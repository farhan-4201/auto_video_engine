"""
Video Compositor — the final stage: burn subtitles, mix optional
background music, and produce the finished 1080p MP4.
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
    """Final composition: subs + music + output."""

    def __init__(self):
        self.assembler = FFmpegAssembler()

    def compose(
        self,
        raw_video: Path,
        srt_path: Path,
        scene_plan: Dict,
        bg_music_file: Optional[Path] = None,
    ) -> Path:
        """
        1. Burn subtitles onto the concatenated video.
        2. Optionally mix background music.
        3. Write final output to output/<topic>_final.mp4
        """
        topic_slug = scene_plan["topic"].lower().replace(" ", "_")[:30]
        style = scene_plan["style"]
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # ── Step 1: burn subtitles ──────────────────────────────
        subbed_path = OUTPUT_DIR / f"{topic_slug}_subbed.mp4"
        self.assembler.burn_subtitles(raw_video, srt_path, subbed_path)

        # ── Step 2: background music (optional) ─────────────────
        if bg_music_file and bg_music_file.exists():
            volume = preset.get("bg_music_volume", 0.08)
            final_path = OUTPUT_DIR / f"{topic_slug}_final.mp4"
            self.assembler.mix_background_music(subbed_path, bg_music_file, final_path, volume)
            # clean intermediate
            subbed_path.unlink(missing_ok=True)
        else:
            final_path = OUTPUT_DIR / f"{topic_slug}_final.mp4"
            subbed_path.rename(final_path)

        logger.info("✅ Final video: %s", final_path)
        return final_path
