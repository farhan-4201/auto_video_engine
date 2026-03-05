"""
Configuration for Auto Video Engine.
All paths, API keys, and defaults live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────
load_dotenv()

# ── Project Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "core"
TEMPLATE_DIR = BASE_DIR / "templates"
MEDIA_DIR = BASE_DIR / "media"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"

# ── API Keys ───────────────────────────────────────────────────
# Get free keys from either provider (only ONE is needed):
#   Pixabay: https://pixabay.com/api/docs/  (recommended — more reliable)
#   Pexels:  https://www.pexels.com/api/
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "YOUR_PIXABAY_API_KEY_HERE")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "YOUR_PEXELS_API_KEY_HERE")

# Which provider to use: "pixabay" | "pexels" | "auto" (tries pixabay first)
MEDIA_PROVIDER = os.environ.get("MEDIA_PROVIDER", "auto")

# ── Video Defaults ─────────────────────────────────────────────
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
VIDEO_BITRATE = "5M"
AUDIO_BITRATE = "192k"
AUDIO_SAMPLE_RATE = 22050

# ── TTS Defaults ───────────────────────────────────────────────
# edge-tts (recommended — free Microsoft neural voices, no build required)
# Run `edge-tts --list-voices` to see 400+ voices
EDGE_TTS_VOICE = "en-US-GuyNeural"        # male narrator (clear, professional)
# Other good options:
#   "en-US-JennyNeural"      — female, warm
#   "en-GB-RyanNeural"       — British male
#   "en-US-AriaNeural"       — female, expressive
#   "en-US-DavisNeural"      — male, casual

# Coqui TTS (optional local fallback — needs `pip install TTS`)
TTS_MODEL = "tts_models/en/ljspeech/tacotron2-DDC"
TTS_SPEAKER = None  # None = default speaker
TTS_LANGUAGE = "en"

# ── Scene Defaults ─────────────────────────────────────────────
DEFAULT_SCENE_DURATION = 6.0       # seconds per scene if TTS is shorter
MIN_SCENE_DURATION = 3.0
MAX_SCENE_DURATION = 15.0
CROSSFADE_DURATION = 0.5           # seconds of crossfade between scenes
SCENE_PADDING = 0.3                # extra seconds after TTS ends

# ── Subtitle Defaults ─────────────────────────────────────────
SUBTITLE_FONT_SIZE = 24
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = "black@0.6"
SUBTITLE_POSITION = "bottom"       # bottom | center
SUBTITLE_MARGIN_V = 40

# ── Style Presets ──────────────────────────────────────────────
STYLE_PRESETS = {
    "documentary": {
        "pexels_orientation": "landscape",
        "pexels_size": "large",
        "scene_transition": "crossfade",
        "bg_music_volume": 0.08,
        "tts_speed": 1.0,
        "color_filter": "none",
    },
    "motivational": {
        "pexels_orientation": "landscape",
        "pexels_size": "large",
        "scene_transition": "crossfade",
        "bg_music_volume": 0.12,
        "tts_speed": 0.95,
        "color_filter": "curves=vintage",
    },
    "educational": {
        "pexels_orientation": "landscape",
        "pexels_size": "large",
        "scene_transition": "fade",
        "bg_music_volume": 0.05,
        "tts_speed": 1.0,
        "color_filter": "none",
    },
    "cinematic": {
        "pexels_orientation": "landscape",
        "pexels_size": "large",
        "scene_transition": "crossfade",
        "bg_music_volume": 0.10,
        "tts_speed": 0.9,
        "color_filter": "colorbalance=bs=.3",
    },
}

# ── FFmpeg ─────────────────────────────────────────────────────
# Auto-detect FFmpeg: try system PATH first, then imageio-ffmpeg bundle
def _find_ffmpeg():
    """Locate ffmpeg binary — checks PATH, then imageio-ffmpeg bundle."""
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg", "ffprobe"
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        # ffprobe lives next to ffmpeg in imageio-ffmpeg bundle (or we skip it)
        from pathlib import Path as _P
        probe = str(_P(ffmpeg_path).parent / "ffprobe-win-x86_64-v7.1.exe")
        if not _P(probe).exists():
            probe = str(_P(ffmpeg_path).with_name(
                _P(ffmpeg_path).name.replace("ffmpeg", "ffprobe")
            ))
        if not _P(probe).exists():
            probe = ffmpeg_path  # will use ffmpeg -i as duration fallback
        return ffmpeg_path, probe
    except ImportError:
        return "ffmpeg", "ffprobe"  # hope it's on PATH

FFMPEG_BIN, FFPROBE_BIN = _find_ffmpeg()

# ── Logging ────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
