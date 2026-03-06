"""
Script Writer — turns (topic, style) into a structured movie-aware narration script.
Uses Google Gemini API (free tier) to generate scripts with real knowledge of the movie:
plot, characters, themes, iconic scenes, and memorable moments.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import GEMINI_API_KEY, GEMINI_MODEL, STYLE_PRESETS

logger = logging.getLogger(__name__)

# ── Movie-aware system prompt ──────────────────────────────────
MOVIE_SYSTEM_PROMPT = """\
You are an expert film critic and YouTube video scriptwriter.
You have deep knowledge of movies — plots, characters, themes, iconic scenes,
cinematography, director's style, cultural impact, and critical reception.

When given a movie title, you write an ENGAGING, ACCURATE narration script that:
1. Mentions real characters by name (e.g. "Tony Stark", "The Joker", "Katniss Everdeen")
2. References actual iconic scenes (e.g. "the interrogation scene", "the hallway fight")
3. Discusses real themes (e.g. "obsession and identity", "survival vs humanity")
4. Includes the director's name and notable cinematography choices
5. Gives the audience real information they'd find in a quality film review/essay

For EACH scene's search_query field, write a YouTube search query that will find
ACTUAL CLIPS or TRAILERS from that specific movie — be precise and movie-specific.

Examples of good search_query values:
  - "Inception corridor fight scene HD"
  - "The Dark Knight Joker interrogation scene"
  - "Interstellar docking scene IMAX"
  - "Parasite official trailer"
  - "No Country for Old Men coin toss scene"

BAD search queries (never do these):
  - "fire explosion action" (too generic)
  - "mountains clouds dramatic" (stock footage keywords)
  - "cinematic landscape" (not movie-specific)

IMPORTANT: Every search_query MUST include the movie title or a key character name.
"""


class ScriptWriter:
    """Generate a movie-aware narration script using Gemini API."""

    def __init__(self):
        self.client = None
        self._setup_gemini()

    def _setup_gemini(self):
        """Initialize Gemini client."""
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            logger.warning("GEMINI_API_KEY not set — script writer will use fallback templates.")
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self.client = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                generation_config={
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "max_output_tokens": 4096,
                    "response_mime_type": "application/json",
                },
                system_instruction=MOVIE_SYSTEM_PROMPT,
            )
            logger.info("Gemini client initialized: model=%s", GEMINI_MODEL)
        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
        except Exception as e:
            logger.error("Gemini setup failed: %s", e)

    # ── public ──────────────────────────────────────────────────
    def generate(self, topic: str, style: str = "documentary", duration: int = 180) -> Dict:
        """
        Return a script dict with movie-aware narration and precise YouTube search queries.
        Falls back to a basic template if Gemini is unavailable.
        """
        if self.client:
            try:
                return self._generate_with_gemini(topic, style, duration)
            except Exception as e:
                logger.error("Gemini script generation failed: %s. Using fallback.", e)

        return self._generate_fallback(topic, style)

    # ── Gemini Generation ──────────────────────────────────────
    def _generate_with_gemini(self, topic: str, style: str, duration: int) -> Dict:
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])
        mood = preset.get("mood", "informative")

        # Detect if topic is likely a movie
        movie_hint = self._detect_movie_context(topic)

        user_prompt = f"""
Create a professional {style} YouTube video script about the movie '{topic}'.
Target duration: {duration} seconds ({duration // 6} to {duration // 5} scenes).
Tone: {mood}, engaging, informative.

{movie_hint}

REQUIREMENTS:
1. STRONG HOOK in scene 1 — grab attention with a bold claim or iconic moment from the film.
2. Narration must reference REAL details: character names, actor names, director, iconic scenes, themes.
3. Each scene's "search_query" must be a precise YouTube search that will find actual clips/trailers
   from THIS specific movie — always include the movie title or main character name in the query.
4. Vary query types across scenes: use trailer, specific scene, behind the scenes, review clips.
5. The final scene should be a strong conclusion — legacy, impact, or recommendation.

Return ONLY valid JSON in this exact format:
{{
    "topic": "{topic}",
    "is_movie": true,
    "director": "Director Name",
    "year": "YYYY",
    "summary": "One sentence about what this video covers",
    "scenes": [
        {{
            "scene_id": 1,
            "type": "intro",
            "narration": "The spoken narration text for this scene...",
            "search_query": "Exact YouTube search query to find a clip from this movie",
            "clip_type": "trailer",
            "emotion": "mystery",
            "intensity": 0.7,
            "pacing": "slow",
            "camera_move": "dolly_in",
            "color_grade": "cold_desaturated",
            "music_cue": "swell_up",
            "cut_style": "fade_black",
            "estimated_duration": 8.0
        }}
    ]
}}

clip_type options: "trailer" | "scene" | "featurette" | "review" | "breakdown"
emotion options: "epic" | "mystery" | "sorrow" | "triumph" | "tension" | "dread"
"""

        logger.info("Calling Gemini API for movie script: %s", topic)
        response = self.client.generate_content(user_prompt)

        raw = response.text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        script = json.loads(raw)
        script["style"] = style

        # Validate and backfill missing fields
        for i, scene in enumerate(script.get("scenes", []), 1):
            scene.setdefault("scene_id", i)
            scene.setdefault("emotion", "epic")
            scene.setdefault("intensity", 0.5)
            scene.setdefault("pacing", "medium")
            scene.setdefault("camera_move", "static_wide")
            scene.setdefault("color_grade", "muted_film")
            scene.setdefault("music_cue", "hold")
            scene.setdefault("cut_style", "hard_cut")
            scene.setdefault("clip_type", "scene")

            # Ensure search_query always includes the movie title
            sq = scene.get("search_query", "")
            if topic.lower() not in sq.lower():
                scene["search_query"] = f"{topic} {sq}".strip()

        logger.info(
            "Gemini script generated: %d scenes for '%s' (%s, %s)",
            len(script["scenes"]), topic,
            script.get("director", "unknown director"),
            script.get("year", "unknown year"),
        )
        return script

    # ── Fallback ───────────────────────────────────────────────
    def _generate_fallback(self, topic: str, style: str) -> Dict:
        """Basic fallback when Gemini is unavailable — still movie-aware via hardcoded queries."""
        logger.warning("Using fallback script for '%s'", topic)
        scenes = []
        queries = [
            f"{topic} official trailer",
            f"{topic} best scenes HD",
            f"{topic} iconic scene",
            f"{topic} movie clip",
            f"{topic} opening scene",
            f"{topic} final scene",
        ]
        narrations = [
            f"Welcome. Today we're diving deep into {topic} — one of the most compelling films ever made.",
            f"From the very first frame, {topic} establishes a world that is impossible to ignore.",
            f"The characters at the heart of {topic} are unforgettable, each one layered with complexity.",
            f"What truly sets {topic} apart is its stunning visual language and masterful direction.",
            f"The themes explored in {topic} resonate long after the credits roll.",
            f"{topic} stands as a landmark achievement in modern cinema. Here's why it matters.",
        ]
        for i, (narration, query) in enumerate(zip(narrations, queries), 1):
            scenes.append({
                "scene_id": i,
                "type": "intro" if i == 1 else ("outro" if i == len(narrations) else "body"),
                "narration": narration,
                "search_query": query,
                "clip_type": "trailer" if i == 1 else "scene",
                "emotion": "epic",
                "intensity": 0.6,
                "pacing": "medium",
                "camera_move": "static_wide",
                "color_grade": "muted_film",
                "music_cue": "swell_up" if i == 1 else ("swell_down" if i == len(narrations) else "hold"),
                "cut_style": "fade_black" if i == 1 else "hard_cut",
                "estimated_duration": 8.0,
            })
        return {
            "topic": topic,
            "style": style,
            "is_movie": True,
            "director": "Unknown",
            "year": "",
            "summary": f"A deep dive into the movie {topic}",
            "scenes": scenes,
        }

    @staticmethod
    def _detect_movie_context(topic: str) -> str:
        """Return extra instructions hinting Gemini about the movie type."""
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["trilogy", "part", "chapter", "episode"]):
            return f"Note: '{topic}' appears to be part of a series — focus on this specific installment."
        if re.search(r"\b(19|20)\d{2}\b", topic):
            return f"Note: The year is specified in the title — reference the correct film."
        return f"Note: Write as if you are a knowledgeable film critic who has seen '{topic}' multiple times."

    def load_external(self, script_path: str) -> Dict:
        """
        Load a user-provided script JSON file, validate required fields,
        and backfill defaults for optional ones.
        """
        path = Path(script_path)
        if not path.exists():
            raise FileNotFoundError(f"Script file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            script = json.load(f)

        # ── Validate top-level fields ─────────────────────────
        if "scenes" not in script or not script["scenes"]:
            raise ValueError("Script JSON must contain a non-empty 'scenes' list.")

        script.setdefault("topic", path.stem)
        script.setdefault("style", "documentary")
        script.setdefault("is_movie", True)
        script.setdefault("director", "Unknown")
        script.setdefault("year", "")
        script.setdefault("summary", f"Video about {script['topic']}")

        # ── Validate & backfill each scene ─────────────────────
        for i, scene in enumerate(script["scenes"], 1):
            if "narration" not in scene or not scene["narration"].strip():
                raise ValueError(f"Scene {i} is missing required 'narration' field.")
            if "search_query" not in scene or not scene["search_query"].strip():
                raise ValueError(f"Scene {i} is missing required 'search_query' field.")

            scene.setdefault("scene_id", i)
            scene.setdefault("type", "intro" if i == 1 else ("outro" if i == len(script["scenes"]) else "body"))
            scene.setdefault("clip_type", "scene")
            scene.setdefault("emotion", "epic")
            scene.setdefault("intensity", 0.5)
            scene.setdefault("pacing", "medium")
            scene.setdefault("camera_move", "static_wide")
            scene.setdefault("color_grade", "muted_film")
            scene.setdefault("music_cue", "hold")
            scene.setdefault("cut_style", "hard_cut")
            scene.setdefault("estimated_duration", 8.0)

        logger.info(
            "Loaded external script: %d scenes from '%s'",
            len(script["scenes"]), path.name,
        )
        return script

    def available_styles(self) -> List[str]:
        return list(STYLE_PRESETS.keys())