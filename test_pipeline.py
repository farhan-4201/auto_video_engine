"""Quick diagnostic test for the video pipeline."""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format='%(name)s | %(levelname)s | %(message)s')

from config import PIXABAY_API_KEY, OPENAI_API_KEY
from core.script_writer import ScriptWriter
from core.scene_builder import SceneBuilder
from core.media_provider import MediaProvider
from core.downloader import MediaDownloader

print("=" * 60)
print("DIAGNOSTIC: Testing pipeline steps individually")
print("=" * 60)

# Check API keys
print(f"\nPixabay key: {'SET' if PIXABAY_API_KEY else 'MISSING'}")
print(f"OpenAI key:  {'SET' if OPENAI_API_KEY else 'MISSING'}")

# Step 1: Script
print("\n--- Step 1: Script Generation ---")
w = ScriptWriter()
script = w.generate("Harry Potter Movie", "documentary", 180)
print(f"Scenes generated: {len(script['scenes'])}")
for s in script["scenes"][:3]:
    sid = s["scene_id"]
    narr = s["narration"][:80]
    print(f"  Scene {sid}: {narr}...")

# Step 2: Scene Plan
print("\n--- Step 2: Scene Plan ---")
b = SceneBuilder()
plan = b.build(script)
for s in plan["scenes"][:3]:
    sid = s["scene_id"]
    kws = s["search_keywords"][:3]
    mt = s["media_type"]
    print(f"  Scene {sid}: keywords={kws}, type={mt}")

# Step 3: Media Search
print("\n--- Step 3: Media Search (Pixabay) ---")
mp = MediaProvider("pixabay")
dl = MediaDownloader()
for scene in plan["scenes"][:3]:
    try:
        results = mp.search(
            keywords=scene["search_keywords"],
            media_type=scene["media_type"],
        )
        print(f"  Scene {scene['scene_id']}: {len(results)} results")
        if results:
            path = dl.download_for_scene(scene, results)
            print(f"    -> media_file = {scene.get('media_file', 'NONE')}")
        else:
            print("    -> NO RESULTS")
    except Exception as e:
        print(f"    -> ERROR: {e}")

# Step 4: TTS test (single scene)
print("\n--- Step 4: TTS (first scene only) ---")
from core.tts_engine import TTSEngine
tts = TTSEngine(project_id="test_harry")
try:
    s0 = plan["scenes"][0]
    audio, timing = tts.synthesize(s0["narration"], s0["scene_id"])
    dur = tts.get_audio_duration(audio)
    print(f"  Audio: {audio}")
    print(f"  Duration: {dur:.1f}s, Word timing entries: {len(timing)}")
except Exception as e:
    print(f"  TTS ERROR: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
