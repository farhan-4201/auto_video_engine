
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(os.getcwd()) / "core"))
from core.pixabay_fetcher import PixabayFetcher
from config import PIXABAY_API_KEY

def test_pixabay():
    print(f"Testing Pixabay with key: {PIXABAY_API_KEY[:5]}...")
    fetcher = PixabayFetcher()
    try:
        results = fetcher.search(["space", "cinematic"], media_type="videos")
        print(f"Success! Found {len(results)} videos.")
        if results:
            print(f"First result: {results[0]['url']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pixabay()
