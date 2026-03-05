"""
Media Provider — unified interface.

Primary: YouTube (via yt-dlp, no API key needed).
Fallback: Wikimedia Commons (also no key needed).
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MediaProvider:
    """
    Unified search interface:

        provider = MediaProvider()
        results  = provider.search(keywords, media_type, orientation, size)
    """

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider or "youtube"
        self._primary = None
        self.provider_name = "unknown"
        self._fallbacks: List = []
        self._init_providers()

    # ── init logic ──────────────────────────────────────────────
    def _init_providers(self):
        if self._provider == "wikimedia":
            self._primary = self._make_wikimedia()
            self.provider_name = "Wikimedia Commons"
            self._fallbacks = [("YouTube", self._make_youtube())]
        else:  # "youtube" or "auto" or anything else
            self._primary = self._make_youtube()
            self.provider_name = "YouTube"
            self._fallbacks = [("Wikimedia Commons", self._make_wikimedia())]

        fb_names = [name for name, _ in self._fallbacks]
        logger.info("Media provider: %s%s",
                     self.provider_name,
                     f" (fallbacks: {', '.join(fb_names)})" if fb_names else "")

    @staticmethod
    def _make_wikimedia():
        from core.wikimedia_fetcher import WikimediaFetcher
        return WikimediaFetcher()

    @staticmethod
    def _make_youtube():
        from core.youtube_fetcher import YouTubeFetcher
        return YouTubeFetcher()

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
