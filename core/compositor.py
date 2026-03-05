"""
Video Compositor — the final stage: burn subtitles, mix optional
background music (with per-scene music_cue automation), and produce
the finished 1080p MP4.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OUTPUT_DIR, MUSIC_DIR, STYLE_PRESETS
from core.ffmpeg_assembler import FFmpegAssembler

logger = logging.getLogger(__name__)


class VideoCompositor:
    """Final composition: subs + music (with cue automation) + output."""

    def __init__(self):
        self.assembler = FFmpegAssembler()

    def compose(
        self,
        raw_video: Path,
        sub_path: Path,
        scene_plan: Dict,
        bg_music_file: Optional[Path] = None,
    ) -> Path:
        """
        1. Burn subtitles (SRT or ASS) onto the concatenated video.
        2. Mix background music with per-scene music_cue automation + ducking.
        3. Write final output.
        """
        topic_slug = scene_plan["topic"].lower().replace(" ", "_")[:30]
        style = scene_plan["style"]
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # ── Step 1: burn subtitles ──────────────────────────────
        subbed_path = OUTPUT_DIR / f"{topic_slug}_subbed.mp4"
        self.assembler.burn_subtitles(raw_video, sub_path, subbed_path)

        # ── Step 2: background music with cue automation ────────
        final_path = OUTPUT_DIR / f"{topic_slug}_final.mp4"
        if final_path.exists():
            final_path.unlink()

        if bg_music_file and bg_music_file.exists():
            scenes = scene_plan.get("scenes", [])
            has_music_cues = any(s.get("music_cue") for s in scenes)

            if has_music_cues:
                # Use the new cue-aware mixer (music_cue + sidechain ducking)
                volume = preset.get("bg_music_volume", 0.08)
                self.assembler.mix_music_with_cues(
                    subbed_path, bg_music_file, final_path,
                    scenes=scenes, base_volume=volume,
                )
            else:
                # Fallback to basic sidechain ducking mix
                volume = preset.get("bg_music_volume", 0.08)
                self.assembler.mix_background_music(
                    subbed_path, bg_music_file, final_path, volume,
                )
            # clean intermediate
            subbed_path.unlink(missing_ok=True)
        else:
            subbed_path.rename(final_path)

        logger.info("Final video: %s", final_path)
        return final_path
