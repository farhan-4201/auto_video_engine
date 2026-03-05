"""
Wikimedia Commons Fetcher — royalty‑free images & videos with NO API key.

API docs: https://www.mediawiki.org/wiki/API:Search
Files live in namespace 6 (File:).  We use imageinfo to get direct URLs.
All media on Wikimedia Commons is freely licensed (CC / public domain).
"""

import logging
import requests
import urllib3
from typing import Dict, List, Optional
from urllib.parse import quote
from requests.adapters import HTTPAdapter

# Suppress only the InsecureRequestWarning for the IP‑fallback path
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

API_URL = "https://commons.wikimedia.org/w/api.php"

# Prefer these extensions (FFmpeg friendly)
VIDEO_EXTS = {".webm", ".ogv", ".mp4"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".svg", ".tiff"}


def _make_session() -> requests.Session:
    """Create a requests session that can survive flaky local DNS
    by resolving via the IP address if needed."""
    s = requests.Session()
    s.headers["User-Agent"] = "AutoVideoEngine/1.0"
    return s


class WikimediaFetcher:
    """Query Wikimedia Commons for royalty‑free media (no API key needed)."""

    # ── public high‑level (same signature as PixabayFetcher) ────
    def search(
        self,
        keywords: List[str],
        media_type: str = "videos",
        orientation: str = "landscape",
        size: str = "large",
    ) -> List[Dict]:
        query = " ".join(keywords[:4])
        logger.info("Wikimedia search [%s]: %s", media_type, query)

        if media_type == "photos":
            return self.search_photos(query, orientation)
        return self.search_videos(query, orientation)

    # ── videos ──────────────────────────────────────────────────
    def search_videos(
        self,
        query: str,
        orientation: str = "landscape",
        per_page: int = 10,
    ) -> List[Dict]:
        """Search Wikimedia Commons for video files."""
        # Append filetype hints to bias towards video results
        search_query = f"{query} filetype:video"
        raw = self._api_search(search_query, per_page=per_page)

        results = []
        for item in raw:
            info = item.get("imageinfo", [{}])[0]
            mime = info.get("mime", "")
            url = info.get("url", "")
            ext = self._ext_from_url(url)

            # Only accept known video formats
            if ext not in VIDEO_EXTS and not mime.startswith("video/"):
                continue

            width = info.get("width", 0)
            height = info.get("height", 0)

            # Skip portrait if landscape requested (and vice versa)
            if orientation == "landscape" and height > width and width > 0:
                continue

            results.append({
                "id": item.get("pageid", 0),
                "width": width,
                "height": height,
                "url": url,
                "duration": info.get("duration", 0),
                "title": item.get("title", ""),
            })

        # If filetype hint returned nothing, do a plain search + filter
        if not results:
            raw = self._api_search(query, per_page=per_page * 2)
            for item in raw:
                info = item.get("imageinfo", [{}])[0]
                mediatype = info.get("mediatype", "")
                mime = info.get("mime", "")
                url = info.get("url", "")
                ext = self._ext_from_url(url)

                if mediatype != "VIDEO" and not mime.startswith("video/") and ext not in VIDEO_EXTS:
                    continue

                width = info.get("width", 0)
                height = info.get("height", 0)
                if orientation == "landscape" and height > width and width > 0:
                    continue

                results.append({
                    "id": item.get("pageid", 0),
                    "width": width,
                    "height": height,
                    "url": url,
                    "duration": info.get("duration", 0),
                    "title": item.get("title", ""),
                })

        logger.info("  → %d video results", len(results))
        return results

    # ── photos ──────────────────────────────────────────────────
    def search_photos(
        self,
        query: str,
        orientation: str = "landscape",
        per_page: int = 10,
    ) -> List[Dict]:
        """Search Wikimedia Commons for image files."""
        raw = self._api_search(query, per_page=per_page * 2)

        results = []
        for item in raw:
            info = item.get("imageinfo", [{}])[0]
            mediatype = info.get("mediatype", "")
            mime = info.get("mime", "")
            url = info.get("url", "")

            # Only accept bitmap images
            if mediatype not in ("BITMAP", "DRAWING") and not mime.startswith("image/"):
                continue
            # Skip SVGs (not great for video backgrounds)
            if mime == "image/svg+xml":
                continue

            width = info.get("width", 0)
            height = info.get("height", 0)

            # Prefer HD+ images
            if width < 1280 and height < 1280:
                continue
            # Orientation filter
            if orientation == "landscape" and height > width and width > 0:
                continue

            # Use thumbnail URL at 1920px if available, else original
            thumb_url = info.get("thumburl", url)
            results.append({
                "id": item.get("pageid", 0),
                "width": info.get("thumbwidth", width),
                "height": info.get("thumbheight", height),
                "url": thumb_url,
                "photographer": info.get("user", "Wikimedia Commons"),
                "title": item.get("title", ""),
            })

        logger.info("  → %d photo results", len(results))
        return results

    # ── core API call ───────────────────────────────────────────
    def _api_search(self, query: str, per_page: int = 10) -> list:
        """
        Generator‑based file search on Wikimedia Commons.
        Returns list of page dicts with 'imageinfo' populated.
        Falls back to direct IP if DNS resolution fails.
        """
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,          # File: namespace
            "gsrlimit": per_page,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|mediatype|user",
            "iiurlwidth": 1920,         # request a 1920px thumbnail
        }

        # Try normal hostname first, then fall back to IP + Host header
        urls_to_try = [
            (API_URL, {}),
            # Direct IP bypass for broken local DNS
            ("https://103.102.166.224/w/api.php",
             {"Host": "commons.wikimedia.org"}),
        ]

        session = _make_session()
        for url, extra_headers in urls_to_try:
            try:
                resp = session.get(
                    url, params=params, timeout=20,
                    headers=extra_headers, verify=(not extra_headers),
                )
                resp.raise_for_status()
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                return sorted(pages.values(),
                              key=lambda p: p.get("index", p.get("pageid", 0)))
            except Exception as exc:
                logger.warning("Wikimedia API error (%s): %s", url[:40], exc)

        return []

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _ext_from_url(url: str) -> str:
        """Extract lowercase file extension from a URL."""
        path = url.split("?")[0]
        dot = path.rfind(".")
        if dot == -1:
            return ""
        return path[dot:].lower()
