"""
Script Writer — turns (topic, style) into a structured narration script.
Upgraded to use LLMs (OpenAI) for cinematic storytelling, hooks, and AI video prompts.
Now generates emotion-aware, cinema-grade visual prompts with full scene metadata.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OPENAI_API_KEY, LLM_MODEL, STYLE_PRESETS

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "script_templates.json"

# ── Cinematic system prompt ────────────────────────────────────
CINEMATIC_SYSTEM_PROMPT = """\
You are a world-class cinematic YouTube scriptwriter AND visual director.
You write narration AND direct every frame like a top-tier documentary filmmaker.

═══ VISUAL PROMPT FORMULA (MANDATORY FOR EVERY SCENE) ═══
Every visual_prompt MUST follow this exact 4-part structure:
  [Camera movement] + [Subject & specific action] + [Emotional atmosphere] + [Lighting & film style]

Examples by emotion:
• TENSE narration → "Slow dolly in on a man's trembling hands gripping a steel railing, claustrophobic framing with shallow depth of field, cold fluorescent lighting with desaturated teal grade, shot on Arri Alexa with anamorphic lens flare"
• EPIC narration → "Wide sweeping crane shot over vast mountain ridges as clouds part to reveal golden valleys below, awe-inspiring scale with tiny human silhouette, golden hour backlight with warm amber tones, shot on 65mm IMAX film stock"
• MYSTERIOUS narration → "Slow push-in through heavy fog toward a half-open door in an abandoned corridor, negative space dominates the frame with deep shadows, low-key lighting with cool blue undertones and volumetric haze, Fincher-style digital intermediate"
• SORROWFUL narration → "Extreme close-up of a single raindrop sliding down a window pane with a blurred cityscape behind, rack focus from foreground to distant lights, overcast natural light with desaturated muted film palette, shot on vintage Cooke lenses"
• TRIUMPHANT narration → "Low-angle tracking shot of a figure walking toward camera against a blazing sunset sky, heroic composition with dust particles catching light, warm golden hour with lens flare, Deakins-style natural lighting on film"

═══ EMOTION-TO-VISUAL RULES (FOLLOW STRICTLY) ═══
The visual_prompt must match the EMOTION of the narration, not merely illustrate the topic:
• Dread → tight framing, cold light, stillness, shallow DOF, close angles
• Epic → wide sweeping shots, golden hour, slow motion feel, vast scale
• Mystery → negative space, fog/haze, low light, slow push-in, cool tones
• Sorrow → close-ups, desaturated, rain/dust/particles, rack focus, soft light
• Triumph → low angles, golden backlight, hero framing, warm tones, flare
• Tension → handheld feel, dutch angle, quick reframing, high contrast, shadow

═══ SCENE JSON FIELDS (ALL REQUIRED) ═══
For each scene you MUST fill ALL of these fields:
- "narration": the spoken text
- "emotion": one of "dread" | "epic" | "mystery" | "sorrow" | "triumph" | "tension"
- "intensity": float 0.0 to 1.0 (how strong the emotion is)
- "pacing": "slow" | "medium" | "fast"
- "visual_prompt": the 4-part cinematic prompt described above
- "camera_move": one of "dolly_in" | "dolly_back" | "tracking" | "static_wide" | "crane_down" | "push_close" | "pan_left" | "pan_right"
- "color_grade": one of "cold_desaturated" | "warm_golden" | "teal_orange" | "high_contrast" | "muted_film"
- "music_cue": one of "swell_up" | "swell_down" | "hold" | "silence"
- "cut_style": one of "hard_cut" | "dissolve" | "fade_black"
- "keywords": list of 3-5 visual noun keywords for stock footage search (NO trademarked names, only visual descriptors)

Choose emotion, camera_move, color_grade, music_cue, and cut_style based on the NARRATIVE CONTEXT of each scene.
Scene 1 should usually start with "swell_up" music_cue. The final scene should use "swell_down" or "fade_black".
Vary emotions across scenes for dramatic arc — not every scene should be the same emotion.
"""


class ScriptWriter:
    """Generate a narration script from a topic and a style preset."""

    def __init__(self):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            self.templates: Dict = json.load(f)
        
        self.client = None
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            except ImportError:
                logger.warning("OpenAI package not found. Falling back to templates.")

    # ── public ──────────────────────────────────────────────────
    def generate(self, topic: str, style: str = "documentary", duration: int = 180) -> Dict:
        """
        Return a script dict. If OpenAI is available, it generates a cinematic script.
        Otherwise, falls back to local templates.
        """
        if self.client:
            try:
                return self._generate_ai(topic, style, duration)
            except Exception as e:
                logger.error(f"AI Script generation failed: {e}. Falling back to templates.")

        return self._generate_template(topic, style)

    # ── AI Generation ──────────────────────────────────────────
    def _generate_ai(self, topic: str, style: str, duration: int) -> Dict:
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["documentary"])
        mood = preset.get("mood", "informative")
        
        user_prompt = f"""
Create a professional {style} video script about '{topic}'.
Target duration: {duration} seconds.
Tone: {mood}, cinematic, engaging.

Requirements:
1. STRONG HOOK in scene 1 (first 5 seconds — grab attention immediately).
2. Break into 10-15 scenes with a clear dramatic arc (setup → rising action → climax → resolution).
3. Every scene's visual_prompt MUST follow the 4-part formula: [Camera movement] + [Subject & action] + [Emotional atmosphere] + [Lighting & film style].
4. Match visuals to the EMOTION of the narration, not just the topic.
5. For 'keywords', use VISUAL NOUNS found on stock sites (e.g., 'ancient castle corridor', 'mystical library'). NO trademarked names.

Return ONLY valid JSON in this exact format:
{{
    "topic": "{topic}",
    "summary": "...",
    "scenes": [
        {{
            "scene_id": 1,
            "type": "intro",
            "narration": "...",
            "emotion": "mystery",
            "intensity": 0.7,
            "pacing": "slow",
            "visual_prompt": "[Camera movement] + [Subject & action] + [Emotional atmosphere] + [Lighting & film style]",
            "camera_move": "dolly_in",
            "color_grade": "cold_desaturated",
            "music_cue": "swell_up",
            "cut_style": "fade_black",
            "keywords": ["visual_noun_1", "visual_noun_2", "visual_noun_3"],
            "estimated_duration": 8.0
        }}
    ]
}}
"""

        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": CINEMATIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"}
        )

        script = json.loads(response.choices[0].message.content)
        script["style"] = style

        # Validate and backfill any missing cinematic fields
        for scene in script.get("scenes", []):
            scene.setdefault("emotion", "epic")
            scene.setdefault("intensity", 0.5)
            scene.setdefault("pacing", "medium")
            scene.setdefault("camera_move", "static_wide")
            scene.setdefault("color_grade", "muted_film")
            scene.setdefault("music_cue", "hold")
            scene.setdefault("cut_style", "hard_cut")

        return script

    # ── Template Fallback ──────────────────────────────────────
    # Emotion mapping for template-based generation (heuristic)
    _TEMPLATE_EMOTION_MAP = {
        "intro": ("mystery", 0.6, "slow", "dolly_in", "cold_desaturated", "swell_up", "fade_black"),
        "body": ("epic", 0.5, "medium", "tracking", "muted_film", "hold", "hard_cut"),
        "outro": ("triumph", 0.7, "slow", "dolly_back", "warm_golden", "swell_down", "dissolve"),
    }

    def _generate_template(self, topic: str, style: str) -> Dict:
        if style not in self.templates:
            style = "documentary"

        tpl = self.templates[style]
        scenes: List[Dict] = []
        scene_id = 1

        # Combine all parts into scenes
        raw_scenes = [tpl["intro"]] + tpl["scenes"] + [tpl["outro"]]
        
        for i, text in enumerate(raw_scenes):
            scene_type = "intro" if i == 0 else ("outro" if i == len(raw_scenes) - 1 else "body")
            emo, intensity, pacing, cam, color, music, cut = self._TEMPLATE_EMOTION_MAP[scene_type]
            
            # Vary emotion across body scenes for a dramatic arc
            if scene_type == "body":
                body_emotions = [
                    ("epic", 0.5, "medium", "tracking", "warm_golden", "hold", "hard_cut"),
                    ("mystery", 0.6, "slow", "dolly_in", "cold_desaturated", "hold", "dissolve"),
                    ("tension", 0.7, "fast", "push_close", "high_contrast", "hold", "hard_cut"),
                    ("epic", 0.8, "medium", "crane_down", "teal_orange", "swell_up", "hard_cut"),
                    ("sorrow", 0.5, "slow", "static_wide", "muted_film", "hold", "dissolve"),
                    ("triumph", 0.9, "fast", "tracking", "warm_golden", "swell_up", "hard_cut"),
                    ("dread", 0.6, "slow", "dolly_back", "cold_desaturated", "silence", "fade_black"),
                    ("mystery", 0.7, "medium", "pan_left", "teal_orange", "hold", "dissolve"),
                    ("epic", 0.6, "medium", "crane_down", "warm_golden", "hold", "hard_cut"),
                    ("tension", 0.8, "fast", "push_close", "high_contrast", "swell_up", "hard_cut"),
                    ("triumph", 0.9, "medium", "tracking", "warm_golden", "swell_up", "dissolve"),
                    ("sorrow", 0.4, "slow", "static_wide", "muted_film", "swell_down", "fade_black"),
                ]
                body_idx = (i - 1) % len(body_emotions)
                emo, intensity, pacing, cam, color, music, cut = body_emotions[body_idx]

            narration = text.format(topic=topic)
            scenes.append({
                "scene_id": scene_id,
                "type": scene_type,
                "narration": narration,
                "emotion": emo,
                "intensity": intensity,
                "pacing": pacing,
                "visual_prompt": f"Cinematic {cam.replace('_', ' ')} shot of {topic}, {emo} atmosphere, film-grade lighting",
                "camera_move": cam,
                "color_grade": color,
                "music_cue": music,
                "cut_style": cut,
                "keywords": [topic, style],
                "estimated_duration": 6.0,
            })
            scene_id += 1

        return {
            "topic": topic,
            "style": style,
            "scenes": scenes,
        }

    def available_styles(self) -> List[str]:
        return list(self.templates.keys())
