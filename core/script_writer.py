"""
Script Writer — turns (topic, style) into a structured narration script.
Loads templates from templates/script_templates.json and fills them.
"""

import json
from pathlib import Path
from typing import Dict, List

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "script_templates.json"


class ScriptWriter:
    """Generate a narration script from a topic and a style preset."""

    def __init__(self):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            self.templates: Dict = json.load(f)

    # ── public ──────────────────────────────────────────────────
    def generate(self, topic: str, style: str = "documentary") -> Dict:
        """
        Return a script dict:
        {
            "topic": str,
            "style": str,
            "scenes": [
                {"scene_id": 1, "type": "intro", "narration": "..."},
                {"scene_id": 2, "type": "body",  "narration": "..."},
                ...
                {"scene_id": N, "type": "outro", "narration": "..."},
            ]
        }
        """
        if style not in self.templates:
            raise ValueError(
                f"Unknown style '{style}'. Available: {list(self.templates.keys())}"
            )

        tpl = self.templates[style]
        scenes: List[Dict] = []
        scene_id = 1

        # intro
        scenes.append({
            "scene_id": scene_id,
            "type": "intro",
            "narration": tpl["intro"].format(topic=topic),
        })
        scene_id += 1

        # body scenes
        for body_text in tpl["scenes"]:
            scenes.append({
                "scene_id": scene_id,
                "type": "body",
                "narration": body_text.format(topic=topic),
            })
            scene_id += 1

        # outro
        scenes.append({
            "scene_id": scene_id,
            "type": "outro",
            "narration": tpl["outro"].format(topic=topic),
        })

        return {
            "topic": topic,
            "style": style,
            "scenes": scenes,
        }

    def available_styles(self) -> List[str]:
        return list(self.templates.keys())
