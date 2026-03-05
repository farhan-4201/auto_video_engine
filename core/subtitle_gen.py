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
    def generate_srt(self, scene_plan: Dict, max_chars_per_line: int = 42) -> Path:
        """
        Walk the scene plan and produce an SRT file with per‑sentence cues.

        Uses TTS durations for accurate timing.  Each narration is split
        into sentences; timing is distributed proportionally by word count.
        """
        srt_path = self.output_dir / "subtitles.srt"
        cues: List[str] = []
        cue_index = 1
        timeline_offset = 0.0  # running clock in seconds

        for scene in scene_plan["scenes"]:
            tts_dur = scene.get("tts_duration", scene.get("estimated_duration", 5.0))
            narration = scene["narration"]

            # split into sentences
            sentences = self._split_sentences(narration)
            total_words = sum(len(s.split()) for s in sentences)
            if total_words == 0:
                timeline_offset += tts_dur + SCENE_PADDING
                continue

            sentence_offset = timeline_offset
            for sentence in sentences:
                word_count = len(sentence.split())
                sentence_dur = (word_count / total_words) * tts_dur
                start = sentence_offset
                end = sentence_offset + sentence_dur

                # wrap long lines
                lines = self._wrap(sentence, max_chars_per_line)

                cues.append(
                    f"{cue_index}\n"
                    f"{self._ts(start)} --> {self._ts(end)}\n"
                    f"{lines}\n"
                )
                cue_index += 1
                sentence_offset = end

            timeline_offset += tts_dur + SCENE_PADDING

        srt_text = "\n".join(cues)
        srt_path.write_text(srt_text, encoding="utf-8")
        logger.info("SRT written: %s (%d cues)", srt_path.name, cue_index - 1)
        return srt_path

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Naive sentence splitter on . ! ?"""
        import re
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _wrap(text: str, max_len: int) -> str:
        """Wrap text into lines of ≤max_len characters."""
        words = text.split()
        lines, current = [], ""
        for w in words:
            if current and len(current) + 1 + len(w) > max_len:
                lines.append(current)
                current = w
            else:
                current = f"{current} {w}".strip()
        if current:
            lines.append(current)
        return "\n".join(lines)

    @staticmethod
    def _ts(seconds: float) -> str:
        """Convert seconds → SRT timestamp  HH:MM:SS,mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
