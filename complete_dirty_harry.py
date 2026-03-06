"""
Complete the pipeline from the raw_concat.mp4 stage
(subtitle generation + final composition).
"""
import sys, os, json, logging, traceback
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from config import TEMP_DIR, OUTPUT_DIR, MUSIC_DIR
from core.subtitle_gen import SubtitleGenerator
from core.compositor import VideoCompositor

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("completer")

PROJECT_ID = "dirty_harry_explained_in_2_min_cinematic"
project_temp = TEMP_DIR / PROJECT_ID

try:
    # Load scene plan
    plan_path = project_temp / "scene_plan.json"
    with open(plan_path) as f:
        scene_plan = json.load(f)
    logger.info("Loaded scene plan: %d scenes", len(scene_plan["scenes"]))

    raw_video = project_temp / "raw_concat.mp4"
    if not raw_video.exists():
        raise FileNotFoundError(f"raw_concat.mp4 not found at {raw_video}")
    logger.info("raw_concat.mp4 size: %.1f MB", raw_video.stat().st_size / 1e6)

    # Generate subtitles
    logger.info("Generating ASS subtitles...")
    subtitler = SubtitleGenerator(PROJECT_ID)
    sub_path = subtitler.generate_ass(scene_plan)
    logger.info("Subtitles written: %s", sub_path)

    # Find background music
    bg_music_path = None
    music_files = list(MUSIC_DIR.glob("*.mp3"))
    if music_files:
        bg_music_path = music_files[0]
        logger.info("Background music: %s", bg_music_path)
    else:
        logger.info("No background music found")

    # Final composition
    logger.info("Starting final composition...")
    compositor = VideoCompositor()
    final = compositor.compose(raw_video, sub_path, scene_plan, bg_music_path)
    logger.info("DONE! Final video: %s", final)
    print(f"\nFinal video: {final}")

except Exception as e:
    logger.error("Pipeline failed: %s", e)
    traceback.print_exc()
