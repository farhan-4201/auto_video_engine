"""
Media Provider — unified interface that auto‑selects between
Pixabay (preferred) and Pexels with automatic fallback.

If MEDIA_PROVIDER config is "auto", it tries whichever API key
is configured first (Pixabay → Pexels). If one fails at runtime,
it falls back to the other.
"""

import logging
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PIXABAY_API_KEY, PEXELS_API_KEY, MEDIA_PROVIDER

logger = logging.getLogger(__name__)


class MediaProvider:
    """
    Unified search interface.  Usage is identical to PexelsFetcher/PixabayFetcher:

        provider = MediaProvider()          # auto‑picks based on config
        results  = provider.search(keywords, media_type, orientation, size)
    """

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider or MEDIA_PROVIDER  # "auto" | "pixabay" | "pexels"
        self._primary = None
        self._fallback = None
        self.provider_name = "unknown"
        self._init_providers()

    # ── init logic ──────────────────────────────────────────────
    def _init_providers(self):
        pixabay_ok = PIXABAY_API_KEY and PIXABAY_API_KEY != "YOUR_PIXABAY_API_KEY_HERE"
        pexels_ok = PEXELS_API_KEY and PEXELS_API_KEY != "YOUR_PEXELS_API_KEY_HERE"

        if self._provider == "pixabay":
            self._primary = self._make_pixabay()
            self.provider_name = "Pixabay"
            if pexels_ok:
                self._fallback = self._make_pexels()
        elif self._provider == "pexels":
            self._primary = self._make_pexels()
            self.provider_name = "Pexels"
            if pixabay_ok:
                self._fallback = self._make_pixabay()
        else:  # auto
            if pixabay_ok:
                self._primary = self._make_pixabay()
                self.provider_name = "Pixabay"
                if pexels_ok:
                    self._fallback = self._make_pexels()
            elif pexels_ok:
                self._primary = self._make_pexels()
                self.provider_name = "Pexels"
            else:
                raise RuntimeError(
                    "No media API key configured!\n"
                    "Set one of these environment variables:\n"
                    "  PIXABAY_API_KEY  — free at https://pixabay.com/api/docs/\n"
                    "  PEXELS_API_KEY   — free at https://www.pexels.com/api/\n"
                    "Or edit config.py directly."
                )

        logger.info("Media provider: %s%s",
                     self.provider_name,
                     f" (fallback: {'Pexels' if 'Pixabay' in self.provider_name else 'Pixabay'})"
                     if self._fallback else "")

    @staticmethod
    def _make_pixabay():
        from core.pixabay_fetcher import PixabayFetcher
        return PixabayFetcher()

    @staticmethod
    def _make_pexels():
        from core.pexels_fetcher import PexelsFetcher
        return PexelsFetcher()

    # ── public ──────────────────────────────────────────────────
    def search(
        self,
        keywords: List[str],
        media_type: str = "videos",
        orientation: str = "landscape",
        size: str = "large",
    ) -> List[Dict]:
        """Search with auto‑fallback between providers and query broadening."""

        # Build a list of progressively broader queries to try:
        #   1. All keywords  e.g. ["Black Holes", "galaxy", "space"]
        #   2. Just the topic e.g. ["Black Holes"]
        #   3. Topic words    e.g. ["Black", "Holes"]
        queries_to_try = [keywords]
        topic = keywords[0] if keywords else ""
        if len(keywords) > 1:
            queries_to_try.append([topic])           # just the topic phrase
        topic_words = topic.split()
        if len(topic_words) > 1:
            queries_to_try.append(topic_words)        # individual words

        for query_kw in queries_to_try:
            # try primary provider
            result = self._try_provider(self._primary, self.provider_name, query_kw, media_type, orientation, size)
            if result:
                return result
            # try fallback provider
            if self._fallback:
                fallback_name = "Pexels" if "Pixabay" in self.provider_name else "Pixabay"
                result = self._try_provider(self._fallback, fallback_name, query_kw, media_type, orientation, size)
                if result:
                    return result

        # Last resort: try photos if we were searching for videos
        if media_type == "videos":
            logger.info("No videos found — trying photos for '%s'", topic)
            for query_kw in queries_to_try:
                result = self._try_provider(self._primary, self.provider_name, query_kw, "photos", orientation, size)
                if result:
                    return result

        logger.error("All queries exhausted for keywords: %s", keywords)
        return []

    def _try_provider(self, provider, name, keywords, media_type, orientation, size) -> List[Dict]:
        """Single attempt on one provider. Returns results or empty list."""
        try:
            results = provider.search(keywords, media_type, orientation, size)
            if results:
                return results
        except Exception as exc:
            logger.warning("%s failed: %s", name, exc)
        return []
