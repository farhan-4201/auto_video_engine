"""
Orchestrator — single entry-point for the movie video pipeline:

    Input (movie title + style)
            ↓
    Gemini API → Movie-aware narration script
    (real characters, scenes, themes, director, year)
            ↓
    Scene Builder → Scene plan with precise YouTube search queries
    e.g. "The Dark Knight Joker interrogation scene"
    NOT "fire explosion dramatic"
            ↓
    yt-dlp → Download actual movie clips/trailers from YouTube
            ↓
    Quality validation → reject low-res / corrupt clips
            ↓
    edge-tts → Movie-relevant narration audio
            ↓
    Peak detection → power-word visual effects
            ↓
    FFmpeg → Scene assembly (trim clips to EXACT TTS duration)
            ↓
    Final 1080p MP4 with real movie footage + narration (no subtitles)
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, TEMP_DIR, STYLE_PRESETS, MUSIC_DIR
from core.script_writer import ScriptWriter
from core.scene_builder import SceneBuilder
from core.youtube_fetcher import YouTubeFetcher       # ← replaces MediaProvider
from core.tts_engine import TTSEngine
from core.ffmpeg_assembler import FFmpegAssembler
from core.peak_detector import detect_peaks_for_scene_plan
from core.compositor import VideoCompositor

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")


class VideoOrchestrator:
    """
    End-to-end movie video generator.

    Usage:
        orch = VideoOrchestrator()
        final = orch.run(topic="The Dark Knight", style="cinematic")
    """

    def __init__(self):
        self.writer = ScriptWriter()
        self.builder = SceneBuilder()
        self.fetcher = YouTubeFetcher()          # ← yt-dlp based
        self.tts = TTSEngine()
        self.assembler = FFmpegAssembler()
        self.compositor = VideoCompositor()

    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _make_project_id(topic: str, style: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:30]
        return f"{slug}_{style}"

    def run(
        self,
        topic: str,
        style: str = "documentary",
        bg_music: Optional[str] = None,
        script_path: Optional[str] = None,
    ) -> Path:
        t0 = time.time()
        logger.info("=" * 60)
        logger.info("MOVIE PIPELINE START  │  topic=%s  style=%s", topic, style)
        logger.info("=" * 60)

        # ── 0. Project isolation ────────────────────────────────
        project_id = self._make_project_id(topic, style)
        project_temp = TEMP_DIR / project_id
        project_temp.mkdir(parents=True, exist_ok=True)
        self.tts.set_project(project_id)
        self.assembler.set_project(project_id)
        logger.info("Project ID: %s", project_id)

        # ── 1. Load custom script OR generate via Gemini ────────
        if script_path:
            logger.info("STEP 1/6 — Loading user-provided script: %s", script_path)
            script = self.writer.load_external(script_path)
            # Override topic/style from the script if present
            topic = script.get("topic", topic)
            style = script.get("style", style)
        else:
            logger.info("STEP 1/6 — Generating movie-aware script with Gemini…")
            script = self.writer.generate(topic, style)
        logger.info(
            "  Script: %d scenes | director=%s | year=%s | words=%d",
            len(script["scenes"]),
            script.get("director", "?"),
            script.get("year", "?"),
            sum(len(s["narration"].split()) for s in script["scenes"]),
        )
        logger.info("  Sample narration: %s", script["scenes"][0]["narration"][:120])

        # ── 2. Build scene plan ─────────────────────────────────
        logger.info("STEP 2/6 — Building scene plan…")
        scene_plan = self.builder.build(script)
        plan_path = project_temp / "scene_plan.json"
        self.builder.save(scene_plan, plan_path)
        logger.info("  Scene plan saved: %s", plan_path)
        # Log the search queries so user can verify they're movie-specific
        for s in scene_plan["scenes"]:
            logger.info(
                "  Scene %02d [%s]: %s",
                s["scene_id"], s["clip_type"], s["search_query"]
            )

        # ── 3. Download movie clips from YouTube via yt-dlp ─────
        logger.info("STEP 3/6 — Downloading movie clips from YouTube…")
        scene_plan = self.fetcher.fetch_all_scenes(scene_plan)
        self.builder.save(scene_plan, plan_path)

        fetched = sum(1 for s in scene_plan["scenes"] if s.get("media_file"))
        logger.info("  Clips downloaded: %d/%d", fetched, scene_plan["total_scenes"])
        if fetched == 0:
            raise RuntimeError(
                "No clips downloaded. Check your internet connection or try a more popular movie."
            )

        # ── 3b. Quality validation — reject low-res / corrupt clips
        logger.info("STEP 3b — Validating clip quality…")
        for scene in scene_plan["scenes"]:
            if scene.get("media_file"):
                qinfo = self.assembler.validate_clip_quality(Path(scene["media_file"]))
                if not qinfo["acceptable"]:
                    logger.warning(
                        "  Scene %d — clip rejected (reason: %s), will re-fetch",
                        scene["scene_id"], qinfo["reason"]
                    )
                    scene["media_file"] = None  # mark for re-fetch or skip
                else:
                    logger.info(
                        "  Scene %d — clip OK (%dx%d, %.1fs)",
                        scene["scene_id"], qinfo["width"], qinfo["height"], qinfo["duration"]
                    )
        self.builder.save(scene_plan, plan_path)

        # ── 4. TTS — movie-aware narration ──────────────────────
        logger.info("STEP 4/6 — Synthesizing movie narration (edge-tts)…")
        scene_plan = self.tts.synthesize_scenes(scene_plan)
        self.builder.save(scene_plan, plan_path)

        # ── 4b. Peak detection — power-word visual effects ───────
        # Only for cinematic styles — documentary/educational use clean footage
        if style in ("cinematic", "motivational"):
            logger.info("STEP 4b — Detecting narration peak events…")
            scene_plan = detect_peaks_for_scene_plan(scene_plan)
            self.builder.save(scene_plan, plan_path)
        else:
            logger.info("STEP 4b — Skipping peak detection (clean style: %s)", style)

        # ── 5. Assemble clips + narration via FFmpeg ─────────────
        # FIX: pass peak_events to assembler for visual effects sync
        logger.info("STEP 5/6 — FFmpeg assembly…")
        clip_paths = []
        for scene in scene_plan["scenes"]:
            if scene.get("media_file") and scene.get("tts_file"):
                peak_events = scene.get("peak_events", [])
                clip = self.assembler.build_scene_clip(
                    scene, style, peak_events=peak_events
                )
                clip_paths.append(clip)
            else:
                missing = []
                if not scene.get("media_file"):
                    missing.append("clip")
                if not scene.get("tts_file"):
                    missing.append("tts")
                logger.warning(
                    "  Skipping scene %d (missing: %s)",
                    scene["scene_id"], ", ".join(missing)
                )

        if not clip_paths:
            raise RuntimeError("No clips were built. Check yt-dlp installation and internet access.")

        raw_video = project_temp / "raw_concat.mp4"
        self.assembler.concatenate(clip_paths, raw_video)

        # ── 6. Music mix + final composite (NO subtitles) ────────
        # FIX: removed subtitle generation and burning — clean narrated video only
        logger.info("STEP 6/6 — Music mix & final composition (no subtitles)…")

        bg_music_path = None
        if bg_music:
            bg_music_path = Path(bg_music)
        else:
            music_files = list(MUSIC_DIR.glob("*.mp3"))
            if music_files:
                bg_music_path = music_files[0]

        if bg_music_path:
            logger.info("  Background music: %s", bg_music_path.name)

        final = self.compositor.compose_no_subtitles(
            raw_video, scene_plan, bg_music_path
        )

        elapsed = time.time() - t0
        logger.info("=" * 60)
        logger.info("DONE  │  %.1f s  │  %s", elapsed, final)
        logger.info("=" * 60)
        return final


# ── CLI ────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Movie Video Engine — generate a narrated video about any movie."
    )
    parser.add_argument(
        "topic",
        help="Movie title (e.g. 'The Dark Knight', 'Inception', 'Parasite')"
    )
    parser.add_argument(
        "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="cinematic",
        help="Style preset (default: cinematic)",
    )
    parser.add_argument(
        "--music",
        default=None,
        help="Path to background music MP3 (optional)",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Path to a custom script JSON file (skips AI generation)",
    )
    args = parser.parse_args()

    orch = VideoOrchestrator()
    final_video = orch.run(
        topic=args.topic,
        style=args.style,
        bg_music=args.music,
        script_path=args.script,
    )
    print(f"\nDone! Final video: {final_video}")


if __name__ == "__main__":
    main()