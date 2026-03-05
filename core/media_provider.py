"""
Media Provider — unified interface that auto‑selects between
AI Video (Runway), Stock (Pixabay/Pexels), and Wikimedia.
"""

import logging
import random
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import PIXABAY_API_KEY, PEXELS_API_KEY, MEDIA_PROVIDER, AI_VIDEO_RATIO

logger = logging.getLogger(__name__)


class MediaProvider:
    """
    Unified search interface supporting AI Video and Hybrid modes.
    """

    def __init__(self, provider: Optional[str] = None):
        self._provider = provider or MEDIA_PROVIDER
        self._primary = None
        self._fallbacks = []
        self.provider_name = "unknown"
        self._init_providers()
        
        from core.ai_video_provider import AIVideoProvider
        self.ai_engine = AIVideoProvider()

    def _init_providers(self):
        pixabay_ok = PIXABAY_API_KEY and PIXABAY_API_KEY != "YOUR_PIXABAY_API_KEY_HERE"
        pexels_ok = PEXELS_API_KEY and PEXELS_API_KEY != "YOUR_PEXELS_API_KEY_HERE"

        if self._provider == "ai_video":
            self.provider_name = "AI Video (Runway)"
            self._fallbacks = self._build_fallbacks(pixabay_ok, pexels_ok)
        elif self._provider == "hybrid":
            self.provider_name = "Hybrid (AI + Stock)"
            self._fallbacks = self._build_fallbacks(pixabay_ok, pexels_ok)
        elif self._provider == "pixabay":
            self._primary = self._make_pixabay()
            self.provider_name = "Pixabay"
            self._fallbacks = self._build_fallbacks(False, pexels_ok)
        else:
            self._primary = self._make_pixabay()
            self.provider_name = "Pixabay"
            self._fallbacks = self._build_fallbacks(pixabay_ok, pexels_ok)

    def _build_fallbacks(self, pixabay_ok, pexels_ok):
        fb = []
        if pixabay_ok: fb.append(("Pixabay", self._make_pixabay()))
        if pexels_ok: fb.append(("Pexels", self._make_pexels()))
        return fb

    @staticmethod
    def _make_pixabay():
        from core.pixabay_fetcher import PixabayFetcher
        return PixabayFetcher()

    @staticmethod
    def _make_pexels():
        from core.pexels_fetcher import PexelsFetcher
        return PexelsFetcher()

    # ── public ──────────────────────────────────────────────────
    def get_media_for_scene(self, scene: Dict, use_ai: bool = False) -> List[Dict]:
        """
        Decision engine: Should this scene use AI video or Stock?
        Returns a list of results (either a single AI clip or multiple stock matches).
        """
        visual_prompt = scene.get("visual_prompt", "")
        keywords = scene.get("search_keywords") or scene.get("keywords", [])
        media_type = scene.get("media_type", "videos")
        
        # Hybrid decision
        is_ai_controlled = self._provider in ["ai_video", "hybrid"]
        will_use_ai = use_ai or (self._provider == "hybrid" and random.random() < AI_VIDEO_RATIO)

        if is_ai_controlled and will_use_ai and visual_prompt:
            logger.info(f"Scene {scene['scene_id']}: Using AI Video Generation.")
            ai_url = self.ai_engine.generate(visual_prompt)
            if ai_url:
                return [{"url": ai_url, "provider": "ai_video", "id": "ai_clip"}]
            logger.warning("AI generation failed, falling back to stock.")

        # Fallback to Stock
        return self.search(keywords, media_type=media_type)

    def search(
        self,
        keywords: List[str],
        media_type: str = "videos",
        orientation: str = "landscape",
        size: str = "large",
    ) -> List[Dict]:
        """Classic stock search with fallback."""
        if not keywords: return []

        # Strategy: Subject FIRST, Style SECOND
        # We want the stock engine to find the 'wizard' or 'castle' before it tries to be 'cinematic'
        queries_to_try = [
            keywords + ["cinematic", "4k"], # High quality attempt
            keywords,                       # Raw subject (best for relevance)
            [keywords[0], "cinematic"],     # Broadest match
        ]
        
        providers = ([(self.provider_name, self._primary)] if self._primary else []) + self._fallbacks

        for query_kw in queries_to_try:
            if not query_kw: continue
            # Join keywords into a proper search string if provider demands it
            # But here we just pass the list to the child providers
            for _, prov in providers:
                try:
                    res = prov.search(query_kw, media_type, orientation, size)
                    if res: 
                        logger.info(f"Found {len(res)} matches for: {' '.join(query_kw)}")
                        return res
                except: continue
        
        logger.warning(f"No media found for keywords: {keywords}")
        return []
