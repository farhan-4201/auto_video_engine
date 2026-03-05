"""
Orchestrator — the single entry‑point that runs the full pipeline:

    Input (topic + style)
            ↓
    Script Template (Local)
            ↓
    Scene JSON
            ↓
    Pexels API (free images/videos)
            ↓
    Download
            ↓
    Coqui TTS (local voice)
            ↓
    FFmpeg Scene Assembly
            ↓
    Subtitle from script timing
            ↓
    Final 1080p Video
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
from core.media_provider import MediaProvider
from core.downloader import MediaDownloader
from core.tts_engine import TTSEngine
from core.ffmpeg_assembler import FFmpegAssembler
from core.subtitle_gen import SubtitleGenerator
from core.compositor import VideoCompositor

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")


class VideoOrchestrator:
    """
    End‑to‑end automated video generator.

    Usage:
        orch = VideoOrchestrator()
        final_video = orch.run(topic="Black Holes", style="documentary")
    """

    def __init__(self):
        self.writer = ScriptWriter()
        self.builder = SceneBuilder()
        self.fetcher = MediaProvider()      # auto‑selects Pixabay or Pexels
        self.downloader = MediaDownloader()
        self.tts = TTSEngine()
        self.assembler = FFmpegAssembler()
        self.subtitler = SubtitleGenerator()
        self.compositor = VideoCompositor()

    # ──────────────────────────────────────────────────────────
    # Full pipeline
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _make_project_id(topic: str, style: str) -> str:
        """Slug like 'black_holes_documentary' — safe for filesystem use."""
        slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:30]
        return f"{slug}_{style}"

    def run(
        self,
        topic: str,
        style: str = "documentary",
        bg_music: Optional[str] = None,
    ) -> Path:
        t0 = time.time()
        logger.info("=" * 60)
        logger.info("PIPELINE START  │  topic=%s  style=%s", topic, style)
        logger.info("=" * 60)

        # ── 0. Project isolation ────────────────────────────────
        project_id = self._make_project_id(topic, style)
        project_temp = TEMP_DIR / project_id
        project_temp.mkdir(parents=True, exist_ok=True)
        self.tts.set_project(project_id)
        self.assembler.set_project(project_id)
        self.subtitler.set_project(project_id)
        logger.info("  Project ID: %s", project_id)

        # ── 1. Generate script ──────────────────────────────────
        logger.info("STEP 1/7 — Generating script…")
        script = self.writer.generate(topic, style)
        logger.info(
            "  Script: %d scenes, %d total words",
            len(script["scenes"]),
            sum(len(s["narration"].split()) for s in script["scenes"]),
        )

        # ── 2. Build scene plan ─────────────────────────────────
        logger.info("STEP 2/7 — Building scene plan…")
        scene_plan = self.builder.build(script)
        plan_path = project_temp / "scene_plan.json"
        self.builder.save(scene_plan, plan_path)
        logger.info("  Scene plan saved: %s", plan_path)

        # ── 3. Fetch media (Pixabay / Pexels) ────────────────────
        logger.info("STEP 3/7 — Fetching media (%s)…", self.fetcher.provider_name)
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])
        for scene in scene_plan["scenes"]:
            results = self.fetcher.search(
                keywords=scene["search_keywords"],
                media_type=scene["media_type"],
                orientation=preset["pexels_orientation"],
                size=preset["pexels_size"],
            )
            logger.info(
                "  Scene %d: %d results for '%s'",
                scene["scene_id"],
                len(results),
                " ".join(scene["search_keywords"][:3]),
            )

            # ── 4. Download best match ──────────────────────────
            self.downloader.download_for_scene(scene, results)

        # ── 5. TTS for each scene ───────────────────────────────
        logger.info("STEP 5/7 — Running TTS…")
        scene_plan = self.tts.synthesize_scenes(scene_plan)

        # save updated plan (with TTS durations)
        self.builder.save(scene_plan, plan_path)

        # ── 6. Assemble scene clips + concatenate ───────────────
        logger.info("STEP 6/7 — FFmpeg assembly…")
        clip_paths = []
        for scene in scene_plan["scenes"]:
            if scene.get("media_file") and scene.get("tts_file"):
                clip = self.assembler.build_scene_clip(scene, style)
                clip_paths.append(clip)
            else:
                logger.warning("  Skipping scene %d (missing media or TTS)", scene["scene_id"])

        raw_video = project_temp / "raw_concat.mp4"
        if not clip_paths:
            logger.error("No clips were built \u2014 cannot produce video.")
            logger.error("This usually means Pixabay had no results for your topic.")
            logger.error("Try a broader topic or check your API key.")
            raise RuntimeError("No media clips available. Try a different topic.")

        self.assembler.concatenate(clip_paths, raw_video)

        # ── 7. Subtitles + final composition ────────────────────
        logger.info("STEP 7/7 — Subtitles & final composition…")
        srt_path = self.subtitler.generate_srt(scene_plan)

        bg_music_path = None
        if bg_music:
            bg_music_path = Path(bg_music)
        else:
            # look for any mp3 in assets/music/
            music_files = list(MUSIC_DIR.glob("*.mp3"))
            if music_files:
                bg_music_path = music_files[0]
                logger.info("  Using background music: %s", bg_music_path.name)

        final = self.compositor.compose(raw_video, srt_path, scene_plan, bg_music_path)

        elapsed = time.time() - t0
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE  │  %.1f s  │  %s", elapsed, final)
        logger.info("=" * 60)

        return final


# ── CLI entry point ────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto Video Engine — generate a YouTube video from a topic."
    )
    parser.add_argument("topic", help="Video topic (e.g. 'Black Holes')")
    parser.add_argument(
        "--style",
        choices=list(STYLE_PRESETS.keys()),
        default="documentary",
        help="Visual / narration style preset (default: documentary)",
    )
    parser.add_argument(
        "--music",
        default=None,
        help="Path to background music MP3 (optional)",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "wikimedia", "pixabay", "pexels"],
        default="auto",
        help="Media provider: auto (default=wikimedia first), wikimedia, pixabay, or pexels",
    )
    args = parser.parse_args()

    orch = VideoOrchestrator()
    final_video = orch.run(topic=args.topic, style=args.style, bg_music=args.music)
    print(f"\n🎬 Done! Final video: {final_video}")


if __name__ == "__main__":
    main()
