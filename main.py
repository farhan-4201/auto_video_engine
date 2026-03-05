"""
Orchestrator — the single entry‑point that runs the full cinematic pipeline:

    Input (topic + style)
            ↓
    Cinematic Script (GPT-4o-mini with emotion/camera/color metadata)
            ↓
    Scene JSON (emotion, intensity, pacing, camera_move, color_grade, music_cue, cut_style)
            ↓
    AI Video (Runway Gen-4 with reference-image anchoring) — 75%
    Stock Footage (Pixabay / Pexels / Wikimedia) — 25%
            ↓
    Stock Normalization (24fps, cinematic LUT, grain, vignette)
            ↓
    TTS (ElevenLabs / edge-tts with word-level timestamps)
            ↓
    Peak Detection (power-word visual events)
            ↓
    FFmpeg Assembly (emotion Ken Burns, color grade, peak effects)
            ↓
    Subtitles (ASS karaoke)
            ↓
    Music Mix (per-scene music_cue automation + sidechain ducking)
            ↓
    Final 1080p Cinematic Video
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import OUTPUT_DIR, TEMP_DIR, STYLE_PRESETS, MUSIC_DIR, AI_VIDEO_RATIO
from core.script_writer import ScriptWriter
from core.scene_builder import SceneBuilder
from core.media_provider import MediaProvider
from core.downloader import MediaDownloader
from core.tts_engine import TTSEngine
from core.ffmpeg_assembler import FFmpegAssembler
from core.subtitle_gen import SubtitleGenerator
from core.compositor import VideoCompositor
from core.ai_video_provider import AIVideoProvider
from core.audio_assets_provider import AudioAssetsProvider
from core.peak_detector import detect_peaks_for_scene_plan

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")


class VideoOrchestrator:
    """
    End‑to‑end automated cinematic video generator.

    Usage:
        orch = VideoOrchestrator()
        final_video = orch.run(topic="Black Holes", style="documentary")
    """

    def __init__(self):
        self.writer = ScriptWriter()
        self.builder = SceneBuilder()
        self.fetcher = MediaProvider()
        self.downloader = MediaDownloader()
        self.tts = TTSEngine()
        self.assembler = FFmpegAssembler()
        self.subtitler = SubtitleGenerator()
        self.compositor = VideoCompositor()
        self.ai_video = AIVideoProvider()
        self.audio_assets = AudioAssetsProvider()

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
        logger.info("CINEMATIC PIPELINE START  │  topic=%s  style=%s", topic, style)
        logger.info("=" * 60)

        # ── 0. Project isolation ────────────────────────────────
        project_id = self._make_project_id(topic, style)
        project_temp = TEMP_DIR / project_id
        project_temp.mkdir(parents=True, exist_ok=True)
        self.tts.set_project(project_id)
        self.assembler.set_project(project_id)
        self.subtitler.set_project(project_id)
        logger.info("  Project ID: %s", project_id)

        # ── 1. Generate cinematic script ────────────────────────
        logger.info("STEP 1/8 — Generating cinematic script…")
        script = self.writer.generate(topic, style)
        logger.info(
            "  Script: %d scenes, %d total words",
            len(script["scenes"]),
            sum(len(s["narration"].split()) for s in script["scenes"]),
        )

        # ── 2. Build scene plan (enrich with search metadata) ───
        logger.info("STEP 2/8 — Building scene plan…")
        scene_plan = self.builder.build(script)
        plan_path = project_temp / "scene_plan.json"
        self.builder.save(scene_plan, plan_path)
        logger.info("  Scene plan saved: %s", plan_path)

        # ── 3. AI video generation (Runway Gen-4) ──────────────
        logger.info("STEP 3/8 — AI Video generation (Gen-4, ratio=%.0f%%)…",
                     AI_VIDEO_RATIO * 100)
        total_scenes = len(scene_plan["scenes"])
        ai_scene_count = int(total_scenes * AI_VIDEO_RATIO)

        # Scenes assigned to AI video (first N by ratio)
        ai_scenes = scene_plan["scenes"][:ai_scene_count]
        stock_scenes = scene_plan["scenes"][ai_scene_count:]

        if ai_scenes:
            self.ai_video.generate_for_scenes(ai_scenes)
            # For AI scenes that succeeded, set media_file
            for scene in ai_scenes:
                if scene.get("ai_video_file"):
                    scene["media_file"] = scene["ai_video_file"]

        # ── 4. Fetch stock media for remaining scenes ──────────
        logger.info("STEP 4/8 — Fetching stock media (%s) for %d scenes…",
                     self.fetcher.provider_name, len(stock_scenes))
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])

        # Also fetch stock for any AI scenes that failed
        scenes_needing_stock = stock_scenes + [
            s for s in ai_scenes if not s.get("media_file")
        ]

        for scene in scenes_needing_stock:
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
            self.downloader.download_for_scene(scene, results)

        # ── 5. (Stock normalization folded into scene clip build) ──
        #    build_scene_clip applies 24fps + LUT + grain + vignette
        #    in a single FFmpeg pass to avoid double-encoding.

        # ── 6. TTS for each scene ──────────────────────────────
        logger.info("STEP 5/8 — Running TTS…")
        scene_plan = self.tts.synthesize_scenes(scene_plan)
        self.builder.save(scene_plan, plan_path)

        # ── 7. Peak detection ──────────────────────────────────
        logger.info("STEP 6/8 — Peak detection (power-word events)…")
        scene_plan = detect_peaks_for_scene_plan(scene_plan)

        # ── 8. Assemble scene clips + concatenate ──────────────
        logger.info("STEP 7/8 — FFmpeg assembly (emotion Ken Burns + color grade)…")
        clip_paths = []
        for scene in scene_plan["scenes"]:
            if scene.get("media_file") and scene.get("tts_file"):
                peak_events = scene.get("peak_events", [])
                clip = self.assembler.build_scene_clip(
                    scene, style, peak_events=peak_events or None,
                )
                clip_paths.append(clip)
            else:
                logger.warning("  Skipping scene %d (missing media or TTS)",
                               scene["scene_id"])

        raw_video = project_temp / "raw_concat.mp4"
        if not clip_paths:
            logger.error("No clips were built — cannot produce video.")
            raise RuntimeError("No media clips available. Try a different topic.")

        self.assembler.concatenate(clip_paths, raw_video)

        # ── 9. Subtitles + music cue mix + final composition ───
        logger.info("STEP 8/8 — Subtitles, music cue mix & final composition…")
        sub_path = self.subtitler.generate_ass(scene_plan)

        # Select music: emotion-aware or manual override
        bg_music_path = None
        if bg_music:
            bg_music_path = Path(bg_music)
        else:
            # Try emotion-based music selection first
            bg_music_path = self.audio_assets.get_music_for_scene_emotions(
                scene_plan["scenes"]
            )
            if not bg_music_path:
                # Fallback to any mp3 in assets/music/
                music_files = list(MUSIC_DIR.glob("*.mp3"))
                if music_files:
                    bg_music_path = music_files[0]

        if bg_music_path:
            logger.info("  Background music: %s", bg_music_path.name)

        final = self.compositor.compose(raw_video, sub_path, scene_plan, bg_music_path)

        elapsed = time.time() - t0
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE  │  %.1f s  │  %s", elapsed, final)
        logger.info("=" * 60)

        return final


# ── CLI entry point ────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto Video Engine — generate a cinematic YouTube video from a topic."
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
    print(f"\nDone! Final video: {final_video}")


if __name__ == "__main__":
    main()
