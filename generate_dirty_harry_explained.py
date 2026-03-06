"""
Generate "Dirty Harry Explained in 2 Minutes" — cinematic video with full scenes,
proper narration+subtitles, and cinematic color grading.

Usage:
    python generate_dirty_harry_explained.py
"""

import os
import sys
import logging
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from main import VideoOrchestrator

# The project temp directory — clean it for a fresh run
PROJECT_ID = "dirty_harry_explained_in_2_mi_cinematic"


def clean_cached_clips():
    """Remove cached scene clips and TTS so everything regenerates fresh."""
    from config import TEMP_DIR
    project_dir = TEMP_DIR / PROJECT_ID
    for subdir in ["clips", "tts", "subs"]:
        d = project_dir / subdir
        if d.exists():
            shutil.rmtree(d)
            logging.info("Cleaned: %s", d)


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("dirty_harry_explained")

    script_path = Path(__file__).parent / "scripts" / "dirty_harry_explained.json"
    if not script_path.exists():
        logger.error("Script not found: %s", script_path)
        sys.exit(1)

    # Clean cached clips for fresh generation
    clean_cached_clips()

    orch = VideoOrchestrator()
    logger.info("Starting Dirty Harry Explained pipeline...")
    final = orch.run(
        topic="Dirty Harry Explained in 2 Minutes",
        style="cinematic",
        script_path=str(script_path),
    )
    print(f"\nDone! Final video: {final}")


if __name__ == "__main__":
    run()
