"""
Pixabay Fetcher — free alternative to Pexels for stock photos & videos.
API: https://pixabay.com/api/docs/
Free key: https://pixabay.com/api/docs/#api_search_images (sign up → API key in dashboard)
"""

import logging
import requests
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PIXABAY_API_KEY

logger = logging.getLogger(__name__)

PIXABAY_IMAGE_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"


class PixabayFetcher:
    """Query Pixabay for royalty‑free media matching keywords."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or PIXABAY_API_KEY
        if self.api_key == "YOUR_PIXABAY_API_KEY_HERE":
            raise RuntimeError(
                "Set PIXABAY_API_KEY env var or edit config.py with your free key "
                "from https://pixabay.com/api/docs/"
            )

    # ── public ──────────────────────────────────────────────────
    def search_photos(
        self,
        query: str,
        orientation: str = "horizontal",
        per_page: int = 5,
    ) -> List[Dict]:
        """Return list of {id, width, height, url, photographer}."""
        # Pixabay uses "horizontal" not "landscape"
        if orientation == "landscape":
            orientation = "horizontal"

        params = {
            "key": self.api_key,
            "q": query,
            "orientation": orientation,
            "image_type": "photo",
            "min_width": 1920,
            "min_height": 1080,
            "per_page": per_page,
            "safesearch": "true",
            "editors_choice": "false",
        }
        resp = requests.get(PIXABAY_IMAGE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for hit in data.get("hits", []):
            results.append({
                "id": hit["id"],
                "width": hit.get("imageWidth", 1920),
                "height": hit.get("imageHeight", 1080),
                "url": hit.get("largeImageURL", hit.get("webformatURL", "")),
                "url_large": hit.get("largeImageURL", ""),
                "photographer": hit.get("user", "Unknown"),
            })
        return results

    def search_videos(
        self,
        query: str,
        orientation: str = "horizontal",
        per_page: int = 5,
    ) -> List[Dict]:
        """Return list of {id, width, height, url, duration}."""
        if orientation == "landscape":
            orientation = "horizontal"

        params = {
            "key": self.api_key,
            "q": query,
            "orientation": orientation,
            "per_page": per_page,
            "safesearch": "true",
        }
        resp = requests.get(PIXABAY_VIDEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for hit in data.get("hits", []):
            best = self._pick_best_video(hit.get("videos", {}))
            if best:
                results.append({
                    "id": hit["id"],
                    "width": best.get("width", 1920),
                    "height": best.get("height", 1080),
                    "url": best["url"],
                    "duration": hit.get("duration", 0),
                })
        return results

    def search(
        self,
        keywords: List[str],
        media_type: str = "videos",
        orientation: str = "landscape",
        size: str = "large",  # ignored for Pixabay, kept for API compat
    ) -> List[Dict]:
        """High‑level: search by keyword list, return best results."""
        query = " ".join(keywords[:3])  # Pixabay wants space\u2011separated terms
        logger.info("Pixabay search [%s]: %s", media_type, query)

        if media_type == "photos":
            return self.search_photos(query, orientation)
        return self.search_videos(query, orientation)

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _pick_best_video(videos_dict: Dict) -> Optional[Dict]:
        """
        Pixabay videos come as a dict of sizes:
        {"large": {...}, "medium": {...}, "small": {...}, "tiny": {...}}
        Pick the best HD one.
        """
        for size_key in ("large", "medium", "small", "tiny"):
            vid = videos_dict.get(size_key)
            if vid and vid.get("url"):
                return vid
        return None
