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
        Takes a script dict (either LLM-generated or template-based)
        and ensures it has all fields needed for fetching and rendering.
        """
        style = script.get("style", "documentary")
        topic = script.get("topic", "unknown")
        hint = self.hints.get(style, self.hints["documentary"])

        enriched_scenes: List[Dict] = []

        for scene in script["scenes"]:
            # Prioritize existing fields from LLM, otherwise generate
            narration = scene.get("narration", "")
            keywords = scene.get("keywords") or self._extract_keywords(narration, topic)
            
            # append a style-specific suffix if it's from templates (not LLM)
            if not scene.get("keywords"):
                suffix = hint["keywords_suffix"]
                keywords = keywords + [suffix[scene["scene_id"] % len(suffix)]]

            est_dur = scene.get("estimated_duration") or self._estimate_duration(narration)

            enriched_scenes.append({
                "scene_id": scene["scene_id"],
                "type": scene.get("type", "body"),
                "narration": narration,
                "visual_prompt": scene.get("visual_prompt", f"cinematic footage of {topic}"),
                "search_keywords": keywords,
                "media_type": hint["preferred_type"],
                "estimated_duration": round(est_dur, 2),
                # Cinematic metadata (passthrough from ScriptWriter)
                "emotion": scene.get("emotion", "epic"),
                "intensity": scene.get("intensity", 0.5),
                "pacing": scene.get("pacing", "medium"),
                "camera_move": scene.get("camera_move", "static_wide"),
                "color_grade": scene.get("color_grade", "muted_film"),
                "music_cue": scene.get("music_cue", "hold"),
                "cut_style": scene.get("cut_style", "hard_cut"),
                # Placeholders for later pipeline stages
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
        """Pull visual nouns and the topic as search keywords."""
        # Clean topic (remove trademarked qualifiers if possible)
        clean_topic = topic.replace("Movie", "").replace("Game", "").strip()
        kw = [clean_topic]

        # Extract potential nouns/adjectives from narration
        words = re.findall(r"\b[A-Za-z]{4,}\b", narration)
        
        found = []
        seen = {w.lower() for w in topic.split()}
        seen.update(SceneBuilder.STOP_WORDS)
        
        for w in words:
            wl = w.lower()
            if wl not in seen:
                found.append(wl)
                seen.add(wl)
            
        kw.extend(found[:3])
        if len(kw) < 2:
            kw.extend(topic.split())
            
        return list(dict.fromkeys(kw))[:4]

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
