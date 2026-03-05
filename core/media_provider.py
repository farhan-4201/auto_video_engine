"""
Media Provider — unified interface that auto‑selects between
Wikimedia Commons (preferred, no key needed), Pixabay, and Pexels.

If MEDIA_PROVIDER config is "auto", it uses Wikimedia Commons first,
then falls back to Pixabay / Pexels if an API key is configured.
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

        if self._provider == "wikimedia":
            self._primary = self._make_wikimedia()
            self.provider_name = "Wikimedia Commons"
            self._fallbacks = self._build_fallbacks(pixabay_ok, pexels_ok)
        elif self._provider == "pixabay":
            self._primary = self._make_pixabay()
            self.provider_name = "Pixabay"
            self._fallbacks = self._build_fallbacks(False, pexels_ok, include_wikimedia=True)
        elif self._provider == "pexels":
            self._primary = self._make_pexels()
            self.provider_name = "Pexels"
            self._fallbacks = self._build_fallbacks(pixabay_ok, False, include_wikimedia=True)
        else:  # auto → Wikimedia first (no key needed)
            self._primary = self._make_wikimedia()
            self.provider_name = "Wikimedia Commons"
            self._fallbacks = self._build_fallbacks(pixabay_ok, pexels_ok)

        fb_names = [name for name, _ in self._fallbacks]
        logger.info("Media provider: %s%s",
                     self.provider_name,
                     f" (fallbacks: {', '.join(fb_names)})" if fb_names else "")

    def _build_fallbacks(self, pixabay_ok, pexels_ok, include_wikimedia=False):
        """Return ordered list of (name, fetcher) tuples for fallback."""
        fb = []
        if include_wikimedia:
            fb.append(("Wikimedia Commons", self._make_wikimedia()))
        if pixabay_ok:
            fb.append(("Pixabay", self._make_pixabay()))
        if pexels_ok:
            fb.append(("Pexels", self._make_pexels()))
        return fb

    @staticmethod
    def _make_wikimedia():
        from core.wikimedia_fetcher import WikimediaFetcher
        return WikimediaFetcher()

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

        all_providers = [(self.provider_name, self._primary)] + self._fallbacks

        for query_kw in queries_to_try:
            for prov_name, prov in all_providers:
                result = self._try_provider(prov, prov_name, query_kw, media_type, orientation, size)
                if result:
                    return result

        # Last resort: try photos if we were searching for videos
        if media_type == "videos":
            logger.info("No videos found — trying photos for '%s'", topic)
            for query_kw in queries_to_try:
                for prov_name, prov in all_providers:
                    result = self._try_provider(prov, prov_name, query_kw, "photos", orientation, size)
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
