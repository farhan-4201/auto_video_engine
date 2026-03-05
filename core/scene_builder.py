"""
Scene Builder — converts a narration script into a scene‑level JSON
that includes search keywords for media, estimated duration, and TTS text.
"""

import json
import re
from pathlib import Path
from typing import Dict, List

HINTS_PATH = Path(__file__).resolve().parent.parent / "templates" / "media_search_hints.json"

# rough word‑per‑minute for duration estimation
WPM = 150


class SceneBuilder:
    """Enrich a script dict into a full scene‑plan JSON."""

    def __init__(self):
        with open(HINTS_PATH, "r", encoding="utf-8") as f:
            self.hints: Dict = json.load(f)

    # ── public ──────────────────────────────────────────────────
    def build(self, script: Dict) -> Dict:
        """
        Takes a script dict from ScriptWriter.generate() and returns:
        {
            "topic": str,
            "style": str,
            "total_scenes": int,
            "scenes": [
                {
                    "scene_id": int,
                    "type": str,
                    "narration": str,
                    "search_keywords": [str, ...],
                    "media_type": "photos" | "videos",
                    "estimated_duration": float,   # seconds
                    "tts_file": null,               # filled later
                    "media_file": null,             # filled later
                },
                ...
            ]
        }
        """
        style = script["style"]
        topic = script["topic"]
        hint = self.hints.get(style, self.hints["documentary"])

        enriched_scenes: List[Dict] = []

        for scene in script["scenes"]:
            keywords = self._extract_keywords(scene["narration"], topic)
            # append a style‑specific suffix to improve search quality
            suffix = hint["keywords_suffix"]
            search_kw = keywords + [suffix[scene["scene_id"] % len(suffix)]]

            est_dur = self._estimate_duration(scene["narration"])

            enriched_scenes.append({
                "scene_id": scene["scene_id"],
                "type": scene["type"],
                "narration": scene["narration"],
                "search_keywords": search_kw,
                "media_type": hint["preferred_type"],
                "estimated_duration": round(est_dur, 2),
                "tts_file": None,
                "media_file": None,
            })

        return {
            "topic": topic,
            "style": style,
            "total_scenes": len(enriched_scenes),
            "scenes": enriched_scenes,
        }

    # ── private helpers ─────────────────────────────────────────
    # Common filler words to SKIP when extracting search keywords
    STOP_WORDS = {
        "about", "after", "again", "also", "basic", "basics", "been", "before",
        "begin", "being", "could", "daily", "deeper", "every",
        "explore", "fascinating", "field", "first", "found", "from", "great",
        "have", "here", "impact", "interesting", "into", "just",
        "know", "learn", "lives", "look", "looking", "main", "makes",
        "many", "might", "most", "never", "nothing", "opens", "other",
        "over", "people", "quite", "really", "remarkable", "review",
        "secret", "simple", "simpler", "something", "spent", "start",
        "story", "surprise", "takeaways", "takes", "thank", "that",
        "their", "there", "these", "thing", "think", "three", "today",
        "truly", "understand", "understanding", "watching", "welcome",
        "what", "when", "which", "whose", "world", "would", "years",
        "aspects", "experts", "cannot", "overstated", "facts",
    }

    @staticmethod
    def _extract_keywords(narration: str, topic: str) -> List[str]:
        """Pull the topic as the primary search keyword.

        For stock media search, the *topic itself* is by far the best
        query.  Narration filler words ("today", "explore", "begin")
        produce zero results on stock sites, so we skip them.
        """
        # The topic is always the most important keyword
        kw = [topic]

        # Only add words that are NOT common filler and are 5+ chars
        words = re.findall(r"\b[A-Za-z]{5,}\b", narration)
        seen = {w.lower() for w in topic.split()}
        for w in words:
            wl = w.lower()
            if wl not in seen and wl not in SceneBuilder.STOP_WORDS:
                seen.add(wl)
                kw.append(wl)
            if len(kw) >= 3:
                break
        return kw

    @staticmethod
    def _estimate_duration(narration: str) -> float:
        """Estimate TTS duration in seconds from word count."""
        word_count = len(narration.split())
        duration = (word_count / WPM) * 60
        return max(3.0, duration)

    # ── serialise ───────────────────────────────────────────────
    @staticmethod
    def save(scene_plan: Dict, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(scene_plan, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: Path) -> Dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
