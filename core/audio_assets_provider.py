
"""
Audio Assets Provider — manages background music selection by mood and fetches SFX.
Now supports emotion-based music selection from scene plan metadata.
"""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MUSIC_DIR, ASSETS_DIR

logger = logging.getLogger(__name__)

# Emotion → music mood keyword mapping
_EMOTION_MUSIC_MAP = {
    "dread": ["dark", "horror", "suspense", "eerie", "scary"],
    "epic": ["epic", "cinematic", "orchestral", "heroic", "powerful"],
    "mystery": ["mysterious", "ambient", "suspense", "ethereal", "dark"],
    "sorrow": ["sad", "melancholy", "emotional", "piano", "gentle"],
    "triumph": ["triumph", "uplifting", "victory", "inspiring", "epic"],
    "tension": ["tension", "suspense", "thriller", "pulse", "intense"],
}


class AudioAssetsProvider:
    """Manages music and sound effects (SFX)."""

    def __init__(self):
        self.sfx_dir = ASSETS_DIR / "sfx"
        self.sfx_dir.mkdir(parents=True, exist_ok=True)
        self.music_dir = MUSIC_DIR
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def get_music_for_mood(self, mood: str) -> Optional[Path]:
        """
        Selects an appropriate background music track based on the mood.
        Expects music files to be named like 'inspiring_01.mp3' or 'scary_dark.mp3'.
        """
        all_music = list(self.music_dir.glob("*.mp3"))
        if not all_music:
            return None
            
        # Try to find mood matches
        matches = [m for m in all_music if mood.lower() in m.name.lower()]
        if matches:
            return random.choice(matches)
            
        # Fallback to any music
        return random.choice(all_music)

    def get_music_for_scene_emotions(self, scenes: List[Dict]) -> Optional[Path]:
        """
        Select music that best fits the dominant emotion across the scene plan.
        Analyzes all scene emotions and picks the most common mood family.
        """
        all_music = list(self.music_dir.glob("*.mp3"))
        if not all_music:
            return None

        # Count emotion occurrences to find dominant mood
        emotion_counts: Dict[str, int] = {}
        for scene in scenes:
            emo = scene.get("emotion", "epic")
            emotion_counts[emo] = emotion_counts.get(emo, 0) + 1

        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        mood_keywords = _EMOTION_MUSIC_MAP.get(dominant_emotion, ["cinematic"])

        # Search music files for mood keyword matches
        for keyword in mood_keywords:
            matches = [m for m in all_music if keyword.lower() in m.name.lower()]
            if matches:
                choice = random.choice(matches)
                logger.info("Music selected for emotion '%s': %s",
                            dominant_emotion, choice.name)
                return choice

        # Fallback
        choice = random.choice(all_music)
        logger.info("No emotion-matched music found. Using: %s", choice.name)
        return choice

    def get_sfx_for_scene(self, scene_type: str, narration: str) -> Optional[Path]:
        """
        Returns a path to a sound effect based on scene context.
        Example: 'intro' -> whoosh, 'body' -> ambient underscore.
        """
        # Define mapping of keywords to SFX filenames
        sfx_map = {
            "intro": ["whoosh", "impact"],
            "outro": ["logo", "fade_out"],
            "dramatic": ["cinematic_hit", "low_boom"],
            "tech": ["digital", "glitch"]
        }
        
        # Look for type match
        relevant_tags = sfx_map.get(scene_type, ["ambient"])
        
        # Simple scan of narration for emotional keywords
        if "danger" in narration.lower() or "warning" in narration.lower():
            relevant_tags += sfx_map["dramatic"]

        # Search sfx_dir for matches
        all_sfx = list(self.sfx_dir.glob("*.mp3")) + list(self.sfx_dir.glob("*.wav"))
        matches = [s for s in all_sfx if any(tag in s.name.lower() for tag in relevant_tags)]
        
        if matches:
            return random.choice(matches)
            
        return None
