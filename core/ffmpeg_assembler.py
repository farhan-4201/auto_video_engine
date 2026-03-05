"""
FFmpeg Assembler — build individual scene clips (video + TTS audio)
then concatenate them into a single timeline.

All FFmpeg commands are constructed as lists and run via subprocess.
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    FFMPEG_BIN,
    FFPROBE_BIN,
    TEMP_DIR,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_FPS,
    VIDEO_BITRATE,
    AUDIO_BITRATE,
    CROSSFADE_DURATION,
    SCENE_PADDING,
    DEFAULT_SCENE_DURATION,
    STYLE_PRESETS,
)

logger = logging.getLogger(__name__)


class FFmpegAssembler:
    """Assemble individual scenes and concatenate into one video."""

    def __init__(self, project_id: str = "default"):
        self.clips_dir = TEMP_DIR / project_id / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def set_project(self, project_id: str):
        """Switch to a new project\u2011specific clips directory."""
        self.clips_dir = TEMP_DIR / project_id / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────
    # 1. Build a single scene clip
    # ──────────────────────────────────────────────────────────
    def build_scene_clip(self, scene: Dict, style: str) -> Path:
        """
        Create a single scene clip:
          • Scale / crop the media to 1920×1080
          • Loop a photo to match TTS duration (or trim a video)
          • Mix the TTS audio underneath
          • Apply optional colour filter

        Returns the path of the rendered clip.
        """
        scene_id = scene["scene_id"]
        media_path = Path(scene["media_file"])
        tts_path = Path(scene["tts_file"])
        tts_dur = scene.get("tts_duration", DEFAULT_SCENE_DURATION)
        target_dur = tts_dur + SCENE_PADDING

        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])
        color_filter = preset.get("color_filter", "none")

        out_path = self.clips_dir / f"scene_{scene_id:03d}.mp4"
        if out_path.exists():
            logger.info("Clip cached: %s", out_path.name)
            return out_path

        is_image = media_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")

        vf_chain = self._build_video_filters(color_filter)

        if is_image:
            cmd = self._cmd_image_scene(media_path, tts_path, target_dur, vf_chain, out_path)
        else:
            cmd = self._cmd_video_scene(media_path, tts_path, target_dur, vf_chain, out_path)

        logger.info("Building clip scene %d (%.1fs)…", scene_id, target_dur)
        self._run(cmd)
        return out_path

    # ──────────────────────────────────────────────────────────
    # 2. Concatenate all scene clips
    # ──────────────────────────────────────────────────────────
    def concatenate(self, clip_paths: List[Path], output_path: Path) -> Path:
        """
        Concatenate clips with crossfade using the concat demuxer.
        Writes a filelist.txt and runs ffmpeg concat.
        """
        filelist = self.clips_dir / "filelist.txt"
        with open(filelist, "w", encoding="utf-8") as f:
            for p in clip_paths:
                # escape single quotes in path for ffmpeg
                safe = str(p).replace("'", "'\\''")
                f.write(f"file '{safe}'\n")

        cmd = [
            FFMPEG_BIN, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(filelist),
            "-c:v", "libx264", "-preset", "medium",
            "-b:v", VIDEO_BITRATE,
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-movflags", "+faststart",
            str(output_path),
        ]
        logger.info("Concatenating %d clips → %s", len(clip_paths), output_path.name)
        self._run(cmd)
        return output_path

    # ──────────────────────────────────────────────────────────
    # 3. Burn subtitles onto video
    # ──────────────────────────────────────────────────────────
    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        """Hard‑sub an SRT file onto the video."""
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-vf", f"subtitles='{srt_escaped}':force_style="
                   f"'FontSize=24,PrimaryColour=&HFFFFFF&,"
                   f"OutlineColour=&H40000000&,BorderStyle=3,"
                   f"Outline=1,Shadow=0,MarginV=40'",
            "-c:v", "libx264", "-preset", "medium",
            "-b:v", VIDEO_BITRATE,
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        logger.info("Burning subtitles → %s", output_path.name)
        self._run(cmd)
        return output_path

    # ──────────────────────────────────────────────────────────
    # 4. (Optional) Mix background music
    # ──────────────────────────────────────────────────────────
    def mix_background_music(
        self, video_path: Path, music_path: Path, output_path: Path, volume: float = 0.08
    ) -> Path:
        """Overlay quiet background music under the narration."""
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={volume},afade=t=out:st=0:d=3[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]
        logger.info("Mixing background music → %s", output_path.name)
        self._run(cmd)
        return output_path

    # ──────────────────────────────────────────────────────────
    # FFmpeg command templates (private)
    # ──────────────────────────────────────────────────────────
    def _cmd_image_scene(
        self, img: Path, audio: Path, duration: float, vf: str, out: Path
    ) -> list:
        """
        FFmpeg: still image → video with Ken Burns (slow zoom) + TTS audio.

        Template:
          ffmpeg -y -loop 1 -i IMAGE -i AUDIO
            -vf "scale=...,zoompan=...,FORMAT_FILTER"
            -t DURATION -c:v libx264 -pix_fmt yuv420p -c:a aac OUT
        """
        zoompan = (
            f"zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={int(duration * VIDEO_FPS)}:"
            f"s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}"
        )
        full_vf = f"{zoompan},{vf}" if vf else zoompan
        return [
            FFMPEG_BIN, "-y",
            "-loop", "1", "-i", str(img),
            "-i", str(audio),
            "-vf", full_vf,
            "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-preset", "medium",
            "-b:v", VIDEO_BITRATE,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-shortest",
            str(out),
        ]

    def _cmd_video_scene(
        self, video: Path, audio: Path, duration: float, vf: str, out: Path
    ) -> list:
        """
        FFmpeg: stock video → scaled/cropped + TTS audio overlay.

        Template:
          ffmpeg -y -i VIDEO -i AUDIO
            -vf "scale=...,crop=...,FORMAT_FILTER"
            -t DURATION -c:v libx264 -c:a aac OUT
        """
        scale_crop = (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
        )
        full_vf = f"{scale_crop},{vf}" if vf else scale_crop
        return [
            FFMPEG_BIN, "-y",
            "-i", str(video),
            "-i", str(audio),
            "-vf", full_vf,
            "-t", f"{duration:.2f}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium",
            "-b:v", VIDEO_BITRATE,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-movflags", "+faststart",
            str(out),
        ]

    @staticmethod
    def _build_video_filters(color_filter: str) -> str:
        """Return the colour‑grading portion of the -vf chain (or empty)."""
        if color_filter and color_filter != "none":
            return color_filter
        return ""

    @staticmethod
    def _run(cmd: list):
        """Execute an FFmpeg command and raise on failure."""
        logger.debug("CMD: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("FFmpeg stderr:\n%s", result.stderr[-2000:])
            raise RuntimeError(f"FFmpeg failed (exit {result.returncode})")

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def get_duration(filepath: Path) -> float:
        import re as _re
        # Try ffprobe first
        try:
            result = subprocess.run(
                [
                    FFPROBE_BIN, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(filepath),
                ],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            pass
        # Fallback: parse from ffmpeg -i stderr
        try:
            result = subprocess.run(
                [FFMPEG_BIN, "-i", str(filepath), "-f", "null", "-"],
                capture_output=True, text=True,
            )
            match = _re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
            if match:
                h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
                return h * 3600 + m * 60 + s
        except Exception:
            pass
        return 0.0
