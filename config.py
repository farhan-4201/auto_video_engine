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

# ── Gemini API (Free tier) ─────────────────────────────────────
# Get free key from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")   # free tier, fast

# ── YouTube / yt-dlp ──────────────────────────────────────────
# No API key needed — yt-dlp downloads publicly available YouTube videos.
# Install: pip install yt-dlp
# Max clips to download per scene (pick the best one)
YTDLP_MAX_RESULTS = 3
# Preferred video quality (best ≤1080p to keep file sizes manageable)
YTDLP_FORMAT = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
# YouTube search query templates — appended after the movie title
# e.g.  "Inception official trailer", "Inception best scenes clip"
YTDLP_QUERY_SUFFIXES = [
    "official trailer",
    "best scenes",
    "clip HD",
    "movie scenes",
    "4K clip",
]

# ── Video Defaults ─────────────────────────────────────────────
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
VIDEO_BITRATE = "5M"
AUDIO_BITRATE = "192k"
AUDIO_SAMPLE_RATE = 22050

# ── TTS Defaults ───────────────────────────────────────────────
# edge-tts — free Microsoft neural voices, no build required.
# Run `edge-tts --list-voices` to see 400+ voices.
EDGE_TTS_VOICE = "en-US-GuyNeural"        # male narrator (clear, professional)
# Other good options:
#   "en-US-JennyNeural"   — female, warm
#   "en-GB-RyanNeural"    — British male
#   "en-US-AriaNeural"    — female, expressive

# ── Scene Defaults ─────────────────────────────────────────────
DEFAULT_SCENE_DURATION = 6.0       # seconds per scene if TTS is shorter
MIN_SCENE_DURATION = 3.0
MAX_SCENE_DURATION = 15.0
CROSSFADE_DURATION = 0.5
SCENE_PADDING = 0.3

# ── Subtitle Defaults ─────────────────────────────────────────
SUBTITLE_FONT_SIZE = 24
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_BG_COLOR = "black@0.6"
SUBTITLE_POSITION = "bottom"
SUBTITLE_MARGIN_V = 40

# ── Style Presets ──────────────────────────────────────────────
STYLE_PRESETS = {
    "documentary": {
        "scene_transition": "crossfade",
        "bg_music_volume": 0.08,
        "tts_speed": 1.0,
        "color_filter": "none",
        "mood": "informative",
    },
    "motivational": {
        "scene_transition": "crossfade",
        "bg_music_volume": 0.12,
        "tts_speed": 0.95,
        "color_filter": "curves=vintage",
        "mood": "uplifting",
    },
    "educational": {
        "scene_transition": "fade",
        "bg_music_volume": 0.05,
        "tts_speed": 1.0,
        "color_filter": "none",
        "mood": "academic",
    },
    "cinematic": {
        "scene_transition": "crossfade",
        "bg_music_volume": 0.10,
        "tts_speed": 0.9,
        "color_filter": "colorbalance=bs=.3",
        "mood": "cinematic",
    },
    "review": {
        "scene_transition": "crossfade",
        "bg_music_volume": 0.08,
        "tts_speed": 1.0,
        "color_filter": "none",
        "mood": "analytical",
    },
}

# ── FFmpeg ─────────────────────────────────────────────────────
def _find_ffmpeg():
    """Locate ffmpeg binary — checks PATH, then imageio-ffmpeg bundle."""
    import shutil
    if shutil.which("ffmpeg"):
        return "ffmpeg", "ffprobe"
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        from pathlib import Path as _P
        probe = str(_P(ffmpeg_path).parent / "ffprobe-win-x86_64-v7.1.exe")
        if not _P(probe).exists():
            probe = str(_P(ffmpeg_path).with_name(
                _P(ffmpeg_path).name.replace("ffmpeg", "ffprobe")
            ))
        if not _P(probe).exists():
            probe = ffmpeg_path
        return ffmpeg_path, probe
    except ImportError:
        return "ffmpeg", "ffprobe"

FFMPEG_BIN, FFPROBE_BIN = _find_ffmpeg()

# ── Logging ────────────────────────────────────────────────────
LOG_LEVEL = "INFO"