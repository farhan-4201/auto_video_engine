"""
Pexels Fetcher — search the free Pexels API for stock photos & videos.
Returns direct download URLs ranked by relevance.
"""

import logging
import requests
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PEXELS_API_KEY

logger = logging.getLogger(__name__)

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"


class PexelsFetcher:
    """Query Pexels for royalty‑free media matching keywords."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or PEXELS_API_KEY
        if self.api_key == "YOUR_PEXELS_API_KEY_HERE":
            raise RuntimeError(
                "Set PEXELS_API_KEY env var or edit config.py with your free key "
                "from https://www.pexels.com/api/"
            )
        self.headers = {"Authorization": self.api_key}

    # ── public ──────────────────────────────────────────────────
    def search_photos(
        self,
        query: str,
        orientation: str = "landscape",
        size: str = "large",
        per_page: int = 5,
    ) -> List[Dict]:
        """Return list of {id, width, height, url, photographer}."""
        params = {
            "query": query,
            "orientation": orientation,
            "size": size,
            "per_page": per_page,
        }
        resp = requests.get(PEXELS_PHOTO_URL, headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for photo in data.get("photos", []):
            results.append({
                "id": photo["id"],
                "width": photo["width"],
                "height": photo["height"],
                "url": photo["src"]["original"],        # full‑res
                "url_large": photo["src"]["large2x"],    # 1920px wide
                "photographer": photo["photographer"],
            })
        return results

    def search_videos(
        self,
        query: str,
        orientation: str = "landscape",
        size: str = "large",
        per_page: int = 5,
    ) -> List[Dict]:
        """Return list of {id, width, height, url, duration}."""
        params = {
            "query": query,
            "orientation": orientation,
            "size": size,
            "per_page": per_page,
        }
        resp = requests.get(PEXELS_VIDEO_URL, headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for video in data.get("videos", []):
            # pick the best HD file
            best = self._pick_best_video_file(video.get("video_files", []))
            if best:
                results.append({
                    "id": video["id"],
                    "width": best["width"],
                    "height": best["height"],
                    "url": best["link"],
                    "duration": video.get("duration", 0),
                })
        return results

    def search(
        self,
        keywords: List[str],
        media_type: str = "videos",
        orientation: str = "landscape",
        size: str = "large",
    ) -> List[Dict]:
        """High‑level: search by keyword list, return best results."""
        query = " ".join(keywords[:4])   # Pexels works best with short queries
        logger.info("Pexels search [%s]: %s", media_type, query)

        if media_type == "photos":
            return self.search_photos(query, orientation, size)
        return self.search_videos(query, orientation, size)

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _pick_best_video_file(files: List[Dict]) -> Optional[Dict]:
        """Choose the highest‑quality HD file (prefer 1920×1080)."""
        hd = [f for f in files if f.get("width", 0) >= 1920 and f.get("height", 0) >= 1080]
        if hd:
            return max(hd, key=lambda f: f.get("width", 0))
        # fallback to largest available
        if files:
            return max(files, key=lambda f: f.get("width", 0))
        return None
