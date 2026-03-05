"""
Subtitle Generator — create an SRT file from the scene plan with
accurate timing derived from TTS audio durations.
"""

import logging
from pathlib import Path
from typing import Dict, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import TEMP_DIR, SCENE_PADDING

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Generate SRT subtitles aligned to TTS timing."""

    def __init__(self, project_id: str = "default"):
        self.output_dir = TEMP_DIR / project_id / "subs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def set_project(self, project_id: str):
        """Switch to a new project\u2011specific subs directory."""
        self.output_dir = TEMP_DIR / project_id / "subs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── public ──────────────────────────────────────────────────
    # ── public ──────────────────────────────────────────────────
    def generate_ass(self, scene_plan: Dict) -> Path:
        """
        Generate a cinematic .ass subtitle file with word-by-word highlighting.
        """
        ass_path = self.output_dir / "subtitles.ass"
        
        # ASS Header & Styles
        header = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,60,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,2,10,10,80,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        events = []
        timeline_offset = 0.0

        for scene in scene_plan["scenes"]:
            tts_dur = scene.get("tts_duration", 5.0)
            word_timing = scene.get("word_timing", [])

            if not word_timing:
                # Fallback: sentence-based timing (no word-level data)
                sentences = self._split_sentences(scene["narration"])
                total_words = sum(len(s.split()) for s in sentences) or 1
                sentence_offset = timeline_offset
                for sentence in sentences:
                    wc = len(sentence.split())
                    dur = (wc / total_words) * tts_dur
                    start = sentence_offset
                    end = sentence_offset + dur
                    events.append(
                        f"Dialogue: 0,{self._ass_ts(start)},{self._ass_ts(end)},Default,,0,0,0,,{sentence}"
                    )
                    sentence_offset = end
            else:
                # Word-by-word animation grouped into 3-4 word phrases
                PHRASE_SIZE = 4
                for i in range(0, len(word_timing), PHRASE_SIZE):
                    group = word_timing[i:i + PHRASE_SIZE]
                    phrase_start = timeline_offset + group[0]["start"]
                    last = group[-1]
                    phrase_end = timeline_offset + last["start"] + last.get("duration", 0.4)
                    
                    # Build phrase with current-word highlight
                    phrase_words = [w["word"] for w in group]
                    # Show full phrase, highlight the last word in cyan
                    plain = " ".join(phrase_words[:-1])
                    highlighted = phrase_words[-1]
                    if plain:
                        text = f"{plain} {{\\c&H00FFFF&}}{highlighted}{{\\c&HFFFFFF&}}"
                    else:
                        text = f"{{\\c&H00FFFF&}}{highlighted}{{\\c&HFFFFFF&}}"
                    
                    events.append(
                        f"Dialogue: 0,{self._ass_ts(phrase_start)},{self._ass_ts(phrase_end)},Default,,0,0,0,,{text}"
                    )

            timeline_offset += tts_dur + SCENE_PADDING

        ass_content = "\n".join(header + events)
        ass_path.write_text(ass_content, encoding="utf-8")
        logger.info(f"ASS subtitles written: {ass_path.name}")
        return ass_path

    @staticmethod
    def _ass_ts(seconds: float) -> str:
        """Convert seconds → ASS timestamp H:MM:SS.cc"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100) # centiseconds
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        import re
        return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p.strip()]
