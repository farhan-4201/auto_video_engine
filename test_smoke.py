"""Quick smoke test — import all modules and generate a test script."""

import sys
sys.path.insert(0, ".")

from config import FFMPEG_BIN, EDGE_TTS_VOICE
from core.script_writer import ScriptWriter
from core.scene_builder import SceneBuilder
from core.tts_engine import TTSEngine
from core.ffmpeg_assembler import FFmpegAssembler
from core.subtitle_gen import SubtitleGenerator
from core.compositor import VideoCompositor
from core.downloader import MediaDownloader
from core.pixabay_fetcher import PixabayFetcher
from core.media_provider import MediaProvider

# Test script generation
sw = ScriptWriter()
script = sw.generate("Black Holes", "documentary")
print("Script: {} scenes".format(len(script["scenes"])))
for s in script["scenes"]:
    print("  Scene {} [{}]: {}...".format(s["scene_id"], s["type"], s["narration"][:60]))

# Test scene builder
sb = SceneBuilder()
plan = sb.build(script)
print("\nScene plan: {} scenes".format(plan["total_scenes"]))
for s in plan["scenes"]:
    print("  Scene {}: keywords={}, dur={:.1f}s".format(
        s["scene_id"], s["search_keywords"][:3], s["estimated_duration"]))

print("\nFFmpeg: {}".format(FFMPEG_BIN[-50:]))
print("Voice: {}".format(EDGE_TTS_VOICE))
print("\nAll modules imported OK!")
