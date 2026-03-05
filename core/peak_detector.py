"""
Peak Detector — detects emotionally high-impact words in TTS word timings
and generates visual peak events (zoom punch, flash frame, hard cut)
for integration into the FFmpeg filter_complex timeline.
"""

import logging
import random
from typing import Dict, List

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# Power words — emotionally charged words that trigger visual peaks.
# Curated for documentary, cinematic, and essay-style narration.
# ══════════════════════════════════════════════════════════════════
POWER_WORDS = {
    # Dread / fear
    "terrifying", "horrifying", "deadly", "catastrophic", "devastating",
    "apocalyptic", "nightmarish", "doomed", "lethal", "annihilation",
    "extinction", "collapse", "obliterated", "shattered", "destroyed",
    "death", "killed", "massacre", "slaughter", "terror",
    # Epic / awe
    "incredible", "extraordinary", "magnificent", "legendary", "colossal",
    "monumental", "staggering", "breathtaking", "astonishing", "phenomenal",
    "unbelievable", "massive", "enormous", "epic", "infinite",
    "universe", "billion", "trillion", "million", "forever",
    # Triumph / victory
    "triumph", "victory", "conquered", "unstoppable", "invincible",
    "breakthrough", "revolutionary", "transformed", "liberation", "glory",
    "champion", "heroic", "greatest", "ultimate", "achieved",
    # Mystery / intrigue
    "secret", "hidden", "mysterious", "unknown", "forbidden",
    "enigma", "cryptic", "vanished", "disappeared", "unsolved",
    "conspiracy", "buried", "ancient", "lost", "discovered",
    # Tension / urgency
    "suddenly", "instantly", "explosion", "impact", "critical",
    "emergency", "warning", "danger", "crisis", "urgent",
    "countdown", "deadline", "ticking", "imminent", "inevitable",
    # Sorrow / emotion
    "heartbreaking", "tragic", "devastating", "painful", "grief",
    "tears", "mourning", "suffering", "sacrificed", "abandoned",
    "lonely", "forgotten", "farewell", "shattered", "broken",
    # Revelation / surprise
    "revealed", "shocking", "truth", "actually", "reality",
    "impossible", "unthinkable", "never", "everything", "nothing",
}

# Map: peak event type weights for different emotions
_EMOTION_PEAK_WEIGHTS: Dict[str, Dict[str, float]] = {
    "dread":   {"hard_cut": 0.5, "flash_frame": 0.35, "zoom_punch": 0.15},
    "epic":    {"zoom_punch": 0.55, "hard_cut": 0.30, "flash_frame": 0.15},
    "triumph": {"zoom_punch": 0.60, "flash_frame": 0.20, "hard_cut": 0.20},
    "mystery": {"hard_cut": 0.40, "zoom_punch": 0.10, "flash_frame": 0.50},
    "tension": {"hard_cut": 0.45, "flash_frame": 0.40, "zoom_punch": 0.15},
    "sorrow":  {"zoom_punch": 0.20, "hard_cut": 0.50, "flash_frame": 0.30},
}

# Minimum gap between peak events (seconds) to avoid overload
MIN_PEAK_GAP = 2.5


def detect_peaks(
    word_timings: List[Dict],
    emotion: str = "epic",
    max_peaks_per_scene: int = 3,
) -> List[Dict]:
    """
    Scan word_timings for emotionally impactful words and return peak events.

    Args:
        word_timings: list of {"word": str, "start": float, "duration": float}
                      (start/duration in seconds, scene-local time)
        emotion:      scene emotion — influences which peak type is chosen
        max_peaks_per_scene: cap on events per scene to avoid visual clutter

    Returns:
        list of {"time": float, "type": str, "word": str}
        where type is "zoom_punch" | "flash_frame" | "hard_cut"
    """
    if not word_timings:
        return []

    # Find power-word matches
    candidates = []
    for wt in word_timings:
        word_lower = wt.get("word", "").lower().strip(".,!?;:\"'()[]")
        if word_lower in POWER_WORDS:
            t = wt.get("start", 0.0)
            candidates.append({"time": t, "word": wt["word"]})

    if not candidates:
        return []

    # Enforce minimum gap — keep highest-priority (earliest wins, then spaced)
    filtered: List[Dict] = []
    last_t = -999.0
    for c in candidates:
        if c["time"] - last_t >= MIN_PEAK_GAP:
            filtered.append(c)
            last_t = c["time"]
        if len(filtered) >= max_peaks_per_scene:
            break

    # Assign peak type based on emotion weights
    weights = _EMOTION_PEAK_WEIGHTS.get(emotion, _EMOTION_PEAK_WEIGHTS["epic"])
    types = list(weights.keys())
    probs = list(weights.values())

    peaks = []
    for c in filtered:
        chosen_type = random.choices(types, weights=probs, k=1)[0]
        peaks.append({
            "time": c["time"],
            "type": chosen_type,
            "word": c["word"],
        })

    logger.info("  Detected %d peak events (emotion=%s): %s",
                len(peaks), emotion,
                ", ".join(f"{p['word']}@{p['time']:.1f}s→{p['type']}" for p in peaks))

    return peaks


def detect_peaks_for_scene_plan(scene_plan: Dict) -> Dict:
    """
    Run peak detection across all scenes in a scene plan.
    Attaches 'peak_events' list to each scene dict.

    Args:
        scene_plan: full scene plan dict with scenes[].word_timing

    Returns:
        The same scene_plan dict, mutated with peak_events per scene.
    """
    for scene in scene_plan.get("scenes", []):
        word_timing = scene.get("word_timing", [])
        emotion = scene.get("emotion", "epic")

        peaks = detect_peaks(word_timing, emotion=emotion)
        scene["peak_events"] = peaks

    total = sum(len(s.get("peak_events", [])) for s in scene_plan["scenes"])
    logger.info("Peak detection complete: %d total events across %d scenes",
                total, len(scene_plan["scenes"]))

    return scene_plan
