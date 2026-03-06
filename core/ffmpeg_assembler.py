"""
FFmpeg Assembler — build individual scene clips (video + TTS audio)
then concatenate them into a single timeline.

Upgraded with:
- Stock footage normalization (24fps, cinematic LUT, film grain, vignette)
- Emotion-driven Ken Burns motion
- Peak-event integration (zoom punch, flash frame, hard cut)
- Music sync cue support (swell_up, swell_down, silence, hold)

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

# ══════════════════════════════════════════════════════════════════
# Color grade presets — FFmpeg curves approximations
# ══════════════════════════════════════════════════════════════════
# Kodak 2383 print-film emulation (teal-orange bias, crushed blacks, rolled highlights)
_KODAK_2383_CURVES = (
    "curves="
    "r='0/0.05 0.15/0.12 0.35/0.33 0.65/0.68 0.85/0.82 1/0.92':"
    "g='0/0.04 0.15/0.13 0.35/0.32 0.65/0.65 0.85/0.80 1/0.90':"
    "b='0/0.08 0.15/0.16 0.35/0.36 0.65/0.62 0.85/0.76 1/0.86'"
)

COLOR_GRADE_FILTERS = {
    "cold_desaturated": (
        f"{_KODAK_2383_CURVES},"
        "colorbalance=rs=-0.08:gs=-0.04:bs=0.12:rm=-0.06:gm=-0.02:bm=0.08,"
        "eq=saturation=0.65:contrast=1.08"
    ),
    "warm_golden": (
        f"{_KODAK_2383_CURVES},"
        "colorbalance=rs=0.12:gs=0.06:bs=-0.10:rh=0.06:gh=0.03:bh=-0.08,"
        "eq=saturation=1.10:contrast=1.05:brightness=0.03"
    ),
    "teal_orange": (
        f"{_KODAK_2383_CURVES},"
        "colorbalance=rs=0.10:gs=-0.05:bs=-0.12:rm=-0.08:gm=0.02:bm=0.14,"
        "eq=saturation=1.05:contrast=1.10"
    ),
    "high_contrast": (
        f"{_KODAK_2383_CURVES},"
        "eq=contrast=1.25:saturation=0.85:brightness=-0.02,"
        "unsharp=5:5:0.8:5:5:0"
    ),
    "muted_film": (
        f"{_KODAK_2383_CURVES},"
        "eq=saturation=0.75:contrast=1.02:brightness=0.01"
    ),
}

# Film grain noise filter (strength 6-8, subtle)
_FILM_GRAIN = "noise=c0s=7:c0f=t+u:allf=t"

# Soft vignette
_VIGNETTE = "vignette=PI/5"


class FFmpegAssembler:
    """Assemble individual scenes and concatenate into one video."""

    def __init__(self, project_id: str = "default"):
        self.clips_dir = TEMP_DIR / project_id / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def set_project(self, project_id: str):
        """Switch to a new project-specific clips directory."""
        self.clips_dir = TEMP_DIR / project_id / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════
    # Stock footage normalization (Change #4)
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def normalize_stock_clip(
        input_path: Path,
        output_path: Path,
        color_grade: str = "muted_film",
    ) -> Path:
        """
        Normalize a stock clip to cinematic standards:
        - Force 24fps
        - Apply cinematic LUT (Kodak 2383 curves approximation)
        - Add subtle film grain (noise strength 7)
        - Add soft vignette (PI/5)
        - Apply scene-specific color grade

        Args:
            input_path:  raw stock clip
            output_path: normalized output path
            color_grade: one of COLOR_GRADE_FILTERS keys
        """
        if output_path.exists():
            return output_path

        grade_filter = COLOR_GRADE_FILTERS.get(color_grade, COLOR_GRADE_FILTERS["muted_film"])

        vf = (
            f"fps=24,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
            f"{grade_filter},"
            f"{_FILM_GRAIN},"
            f"{_VIGNETTE}"
        )

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(input_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-b:v", VIDEO_BITRATE,
            "-pix_fmt", "yuv420p",
            "-an",  # strip audio from stock clips
            str(output_path),
        ]

        logger.info("Normalizing stock clip → %s (grade=%s)", output_path.name, color_grade)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("Normalization failed: %s", result.stderr[-500:])
            raise RuntimeError(f"Stock normalization failed for {input_path}")

        return output_path

    # ══════════════════════════════════════════════════════════════
    # Emotion-driven Ken Burns motion (Change #5)
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def _emotion_ken_burns(emotion: str, duration: float, intensity: float = 0.5) -> str:
        """
        Build a zoompan filter string that matches the scene emotion.

        Emotion mapping:
          dread   → slow zoom OUT (pull back, reveal emptiness)
          epic    → slow zoom IN (push toward subject)
          triumph → slow zoom IN (push toward subject)
          mystery → slow pan left or right (searching, uncertain)
          tension → very slight handheld shake (subtle randomised offset)
          sorrow  → static or minimal drift down
        """
        frames = int(duration * VIDEO_FPS)
        w, h = VIDEO_WIDTH, VIDEO_HEIGHT

        if emotion == "dread":
            # Zoom out: start at 1.3x, end at 1.0x
            speed = 0.0015 + (intensity * 0.001)
            return (
                f"zoompan=z='if(lte(zoom,1.0),1.3,max(zoom-{speed:.4f},1.0))':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )
        elif emotion in ("epic", "triumph"):
            # Zoom in: start at 1.0x, push to 1.3-1.5x
            speed = 0.0012 + (intensity * 0.0008)
            return (
                f"zoompan=z='min(zoom+{speed:.4f},1.5)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )
        elif emotion == "mystery":
            # Slow pan left: x drifts from right edge toward left
            return (
                f"zoompan=z='1.15':"
                f"x='iw/2-(iw/zoom/2)+((iw/zoom)*0.10)*(1-on/{frames})':"
                f"y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )
        elif emotion == "tension":
            # Subtle handheld shake: small random offsets around center
            return (
                f"zoompan=z='1.08':"
                f"x='iw/2-(iw/zoom/2)+sin(on*0.3)*4':"
                f"y='ih/2-(ih/zoom/2)+cos(on*0.5)*3':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )
        elif emotion == "sorrow":
            # Static with very slight downward drift
            return (
                f"zoompan=z='1.05':"
                f"x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)+(ih*0.01)*(on/{frames})':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )
        else:
            # Default: gentle zoom in
            return (
                f"zoompan=z='min(zoom+0.0010,1.25)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={frames}:s={w}x{h}:fps={VIDEO_FPS}"
            )

    # ══════════════════════════════════════════════════════════════
    # 1. Build a single scene clip
    # ══════════════════════════════════════════════════════════════
    def build_scene_clip(
        self,
        scene: Dict,
        style: str,
        sfx_path: Optional[Path] = None,
        peak_events: Optional[List[Dict]] = None,
    ) -> Path:
        """
        Create a single scene clip with emotion-driven motion,
        cinematic color grading, and optional peak-event effects.
        """
        scene_id = scene["scene_id"]
        media_path = Path(scene["media_file"])
        tts_path = Path(scene["tts_file"])
        tts_dur = scene.get("tts_duration", DEFAULT_SCENE_DURATION)
        target_dur = tts_dur + SCENE_PADDING

        # Read cinematic metadata from scene JSON (with defaults)
        emotion = scene.get("emotion", "epic")
        intensity = scene.get("intensity", 0.5)
        color_grade = scene.get("color_grade", "muted_film")

        out_path = self.clips_dir / f"scene_{scene_id:03d}.mp4"
        if out_path.exists():
            return out_path

        is_image = media_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")

        # Color grade + grain + vignette filter chain
        grade_filter = COLOR_GRADE_FILTERS.get(color_grade, COLOR_GRADE_FILTERS["muted_film"])
        vf_chain = f"{grade_filter},{_FILM_GRAIN},{_VIGNETTE}"

        # Peak-event overlay filters (zoom punch, flash frame)
        peak_vf = self._build_peak_filters(peak_events, target_dur) if peak_events else ""
        if peak_vf:
            vf_chain = f"{vf_chain},{peak_vf}"

        if is_image:
            cmd = self._cmd_image_scene(
                media_path, tts_path, target_dur, vf_chain, out_path,
                sfx_path, emotion, intensity,
            )
        else:
            cmd = self._cmd_video_scene(
                media_path, tts_path, target_dur, vf_chain, out_path, sfx_path,
            )

        logger.info("Building clip scene %d (%.1fs, emotion=%s)…",
                     scene_id, target_dur, emotion)
        self._run(cmd)
        return out_path

    # ══════════════════════════════════════════════════════════════
    # Peak-event filter builder (used by Change #6)
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def _build_peak_filters(peak_events: List[Dict], duration: float) -> str:
        """
        Convert peak_events into FFmpeg filter expressions.
        Each event: {"time": float, "type": "zoom_punch"|"flash_frame"|"hard_cut"}

        zoom_punch  → scale 1.0→1.04 over 3 frames (~0.1s) then back
        flash_frame → 2-frame white flash then return
        hard_cut    → handled at concat level, not as a filter
        """
        parts = []
        for ev in peak_events:
            t = ev["time"]
            etype = ev["type"]
            if etype == "zoom_punch":
                # Quick zoom punch: 0.1s scale burst at timestamp t
                t_end = t + 0.12
                parts.append(
                    f"zoompan=z='if(between(in_time,{t:.3f},{t_end:.3f}),1.04,1.0)':"
                    f"d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}"
                )
            elif etype == "flash_frame":
                # 2-frame white flash (~0.066s at 30fps)
                t_end = t + 0.066
                parts.append(
                    f"drawbox=x=0:y=0:w={VIDEO_WIDTH}:h={VIDEO_HEIGHT}:"
                    f"color=white@0.85:t=fill:"
                    f"enable='between(t,{t:.3f},{t_end:.3f})'"
                )
        return ",".join(parts)

    # ══════════════════════════════════════════════════════════════
    # 2. Concatenate all scene clips
    # ══════════════════════════════════════════════════════════════
    def concatenate(self, clip_paths: List[Path], output_path: Path) -> Path:
        """Concatenate clips using the concat demuxer."""
        filelist = self.clips_dir / "filelist.txt"
        with open(filelist, "w", encoding="utf-8") as f:
            for p in clip_paths:
                safe = str(p).replace("'", "'\\''")
                f.write(f"file '{safe}'\n")

        cmd = [
            FFMPEG_BIN, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(filelist),
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-b:v", VIDEO_BITRATE,
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-movflags", "+faststart",
            str(output_path),
        ]
        logger.info("Concatenating %d clips → %s", len(clip_paths), output_path.name)
        self._run(cmd)
        return output_path

    # ══════════════════════════════════════════════════════════════
    # 3. Burn subtitles onto video
    # ══════════════════════════════════════════════════════════════
    def burn_subtitles(self, video_path: Path, sub_path: Path, output_path: Path) -> Path:
        """Hard-sub an SRT or ASS file onto the video."""
        sub_escaped = str(sub_path).replace("\\", "/").replace(":", "\\:")
        
        if sub_path.suffix == ".ass":
            vf = f"ass='{sub_escaped}'"
        else:
            vf = (
                f"subtitles='{sub_escaped}':"
                f"force_style='FontSize=32,PrimaryColour=&HFFFFFF&,"
                f"OutlineColour=&H40000000&,BorderStyle=3,Outline=1,"
                f"Shadow=0,MarginV=60'"
            )
            
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-b:v", VIDEO_BITRATE,
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        logger.info("Burning subtitles (%s) → %s", sub_path.suffix, output_path.name)
        self._run(cmd)
        return output_path

    # ══════════════════════════════════════════════════════════════
    # 4. Mix background music with sidechain ducking
    # ══════════════════════════════════════════════════════════════
    def mix_background_music(
        self, video_path: Path, music_path: Path, output_path: Path, volume: float = 0.08
    ) -> Path:
        """Overlay background music with sidechain ducking."""
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={volume}[bg];"
            f"[0:a]asplit[a1][a2];"
            f"[a2]anequalizer=c0 f=400 w=200 g=-15[sidechain];"
            f"[bg][sidechain]sidechaingate=threshold=0.1:ratio=2:attack=20:release=100[ducked];"
            f"[a1][ducked]amix=inputs=2:duration=first:dropout_transition=2",
            "-map", "0:v",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-shortest",
            str(output_path),
        ]
        logger.info("Mixing background music with ducking → %s", output_path.name)
        self._run(cmd)
        return output_path

    # ══════════════════════════════════════════════════════════════
    # 5. Music-cue aware mix (Change #7)
    # ══════════════════════════════════════════════════════════════
    def mix_music_with_cues(
        self,
        video_path: Path,
        music_path: Path,
        output_path: Path,
        scenes: List[Dict],
        base_volume: float = 0.08,
    ) -> Path:
        """
        Mix background music with per-scene volume automation driven
        by the music_cue field, AND sidechain ducking (both active).

        music_cue values:
          swell_up  → fade music from 0.3 to 0.8 volume over 1.5s at scene start
          swell_down → fade music from 0.8 to 0.2 over 1.0s at scene end
          silence   → drop music to 0.05 for entire scene
          hold      → maintain current level
        """
        # Build per-scene volume automation expression for FFmpeg
        # Calculate absolute timeline offsets for each scene
        volume_expr_parts = []
        t = 0.0
        for scene in scenes:
            dur = scene.get("tts_duration", DEFAULT_SCENE_DURATION) + SCENE_PADDING
            cue = scene.get("music_cue", "hold")
            s_start = t
            s_end = t + dur

            if cue == "swell_up":
                # 0.3 → 0.8 over 1.5s from scene start, then hold 0.8
                ramp_end = min(s_start + 1.5, s_end)
                volume_expr_parts.append(
                    f"if(between(t,{s_start:.3f},{ramp_end:.3f}),"
                    f"0.3+(0.5*(t-{s_start:.3f})/1.5),0)"
                )
                volume_expr_parts.append(
                    f"if(between(t,{ramp_end:.3f},{s_end:.3f}),0.8,0)"
                )
            elif cue == "swell_down":
                # hold 0.8 then 0.8 → 0.2 over last 1.0s
                ramp_start = max(s_end - 1.0, s_start)
                volume_expr_parts.append(
                    f"if(between(t,{s_start:.3f},{ramp_start:.3f}),0.8,0)"
                )
                volume_expr_parts.append(
                    f"if(between(t,{ramp_start:.3f},{s_end:.3f}),"
                    f"0.8-(0.6*(t-{ramp_start:.3f})/1.0),0)"
                )
            elif cue == "silence":
                volume_expr_parts.append(
                    f"if(between(t,{s_start:.3f},{s_end:.3f}),0.05,0)"
                )
            else:  # hold
                volume_expr_parts.append(
                    f"if(between(t,{s_start:.3f},{s_end:.3f}),{base_volume},0)"
                )

            t = s_end

        # Combine into single volume expression (sum of non-overlapping segments)
        vol_expr = "+".join(volume_expr_parts) if volume_expr_parts else str(base_volume)

        # The filter chain: music volume automation + sidechain ducking
        filter_complex = (
            f"[1:a]volume='{vol_expr}':eval=frame[bg_cued];"
            f"[0:a]asplit[a1][a2];"
            f"[a2]anequalizer=c0 f=400 w=200 g=-15[sidechain];"
            f"[bg_cued][sidechain]sidechaingate=threshold=0.1:ratio=2:"
            f"attack=20:release=100[ducked];"
            f"[a1][ducked]amix=inputs=2:duration=first:dropout_transition=2"
        )

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-shortest",
            str(output_path),
        ]
        logger.info("Mixing music with cue automation + ducking → %s", output_path.name)
        self._run(cmd)
        return output_path

    # ══════════════════════════════════════════════════════════════
    # FFmpeg command templates (private)
    # ══════════════════════════════════════════════════════════════
    def _cmd_image_scene(
        self,
        img: Path,
        audio: Path,
        duration: float,
        vf: str,
        out: Path,
        sfx: Optional[Path] = None,
        emotion: str = "epic",
        intensity: float = 0.5,
    ) -> list:
        # Emotion-aware Ken Burns
        zoompan = self._emotion_ken_burns(emotion, duration, intensity)
        full_vf = f"{zoompan},{vf}" if vf else zoompan
        
        inputs = ["-loop", "1", "-i", str(img), "-i", str(audio)]
        if sfx:
            inputs += ["-i", str(sfx)]
        
        filter_complex = "[0:v]" + full_vf + "[v]"
        if sfx:
            filter_complex += ";[1:a][2:a]amix=inputs=2:duration=first[a]"
        else:
            filter_complex += ";[1:a]acopy[a]"

        return [
            FFMPEG_BIN, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-profile:v", "high", "-b:v", VIDEO_BITRATE,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            str(out),
        ]

    def _cmd_video_scene(
        self, video: Path, audio: Path, duration: float, vf: str, out: Path,
        sfx: Optional[Path] = None,
    ) -> list:
        scale_crop = (
            f"fps=24,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}"
        )
        full_vf = f"{scale_crop},{vf}" if vf else scale_crop
        
        # Input construction: skip first 1s of source video (skip logos), loop if too short
        video_inputs = ["-ss", "1", "-stream_loop", "-1", "-i", str(video)]
        inputs = video_inputs + ["-i", str(audio)]
        if sfx:
            inputs += ["-i", str(sfx)]

        filter_complex = "[0:v]" + full_vf + "[v]"
        if sfx:
            filter_complex += ";[1:a][2:a]amix=inputs=2:duration=first[a]"
        else:
            filter_complex += ";[1:a]acopy[a]"

        return [
            FFMPEG_BIN, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-t", f"{duration:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-profile:v", "high", "-b:v", VIDEO_BITRATE,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            str(out),
        ]

    @staticmethod
    def _run(cmd: list):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("FFmpeg error: %s", result.stderr[-500:])
            raise RuntimeError("FFmpeg failed")

    @staticmethod
    def get_duration(filepath: Path) -> float:
        try:
            result = subprocess.run(
                [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
                capture_output=True, text=True, check=True
            )
            return float(result.stdout.strip())
        except:
            return 0.0
