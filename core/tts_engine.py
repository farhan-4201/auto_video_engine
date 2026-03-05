"""
TTS Engine — generate narration audio using edge‑tts (Microsoft free neural voices).
Falls back to Coqui TTS → pyttsx3 if edge‑tts is unavailable.

edge‑tts: pip install edge-tts  (no C++ build, works everywhere)
Voices:   run `edge-tts --list-voices` to see 400+ free voices.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    TEMP_DIR,
    TTS_MODEL,
    TTS_SPEAKER,
    TTS_LANGUAGE,
    AUDIO_SAMPLE_RATE,
    FFPROBE_BIN,
    EDGE_TTS_VOICE,
)

logger = logging.getLogger(__name__)


class TTSEngine:
    """Text‑to‑speech with auto‑fallback: edge‑tts → Coqui → pyttsx3."""

    def __init__(self, model_name: Optional[str] = None, project_id: str = "default"):
        self.model_name = model_name or TTS_MODEL
        self.output_dir = TEMP_DIR / project_id / "tts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tts = None
        self._backend = None
        self._edge_voice = EDGE_TTS_VOICE

    def set_project(self, project_id: str):
        """Switch to a new project\u2011specific output directory."""
        self.output_dir = TEMP_DIR / project_id / "tts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── lazy init (tries edge‑tts first) ────────────────────────
    def _init_edge_tts(self):
        try:
            import edge_tts  # noqa: F401
            self._backend = "edge_tts"
            logger.info("edge-tts loaded (voice: %s)", self._edge_voice)
            return True
        except ImportError:
            logger.warning("edge-tts not installed — trying Coqui…")
            return False

    def _init_coqui(self):
        try:
            from TTS.api import TTS as CoquiTTS  # noqa: N811
            self._tts = CoquiTTS(model_name=self.model_name, progress_bar=False)
            self._backend = "coqui"
            logger.info("Coqui TTS loaded: %s", self.model_name)
            return True
        except ImportError:
            logger.warning("Coqui TTS not installed — trying pyttsx3…")
            return False

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", 160)
            self._backend = "pyttsx3"
            logger.info("pyttsx3 TTS loaded (offline fallback)")
            return True
        except ImportError:
            return False

    def _ensure_engine(self):
        if self._backend is not None:
            return
        if self._init_edge_tts():
            return
        if self._init_coqui():
            return
        if self._init_pyttsx3():
            return
        raise RuntimeError(
            "No TTS engine available!\n"
            "Install one:  pip install edge-tts   (recommended, easiest)\n"
            "         or:  pip install TTS         (local neural, needs C++ tools)\n"
            "         or:  pip install pyttsx3     (offline robotic fallback)"
        )

    # ── public ──────────────────────────────────────────────────
    def synthesize(self, text: str, scene_id: int) -> Path:
        """
        Render *text* to an audio file and return its path.
        File: temp/tts/scene_{scene_id}.mp3  (edge‑tts)
              temp/tts/scene_{scene_id}.wav  (coqui / pyttsx3)
        """
        self._ensure_engine()

        if self._backend == "edge_tts":
            out_path = self.output_dir / f"scene_{scene_id}.mp3"
        else:
            out_path = self.output_dir / f"scene_{scene_id}.wav"

        if out_path.exists():
            logger.info("TTS cached: %s", out_path.name)
            return out_path

        logger.info("TTS [%s] scene %d (%d chars)…", self._backend, scene_id, len(text))

        if self._backend == "edge_tts":
            self._synthesize_edge(text, out_path)
        elif self._backend == "coqui":
            kwargs = {}
            if TTS_SPEAKER:
                kwargs["speaker"] = TTS_SPEAKER
            if TTS_LANGUAGE:
                kwargs["language"] = TTS_LANGUAGE
            self._tts.tts_to_file(text=text, file_path=str(out_path), **kwargs)
        else:
            # pyttsx3 fallback
            self._tts.save_to_file(text, str(out_path))
            self._tts.runAndWait()

        logger.info("TTS saved: %s", out_path.name)
        return out_path

    def synthesize_scenes(self, scene_plan: dict) -> dict:
        """Run TTS for every scene in the plan. Updates plan in‑place."""
        for scene in scene_plan["scenes"]:
            audio = self.synthesize(scene["narration"], scene["scene_id"])
            scene["tts_file"] = str(audio)
            scene["tts_duration"] = self.get_audio_duration(audio)
        return scene_plan

    # ── edge‑tts async wrapper ──────────────────────────────────
    def _synthesize_edge(self, text: str, out_path: Path):
        """Run edge‑tts communicate() in a sync context."""
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(text, self._edge_voice)
            await communicate.save(str(out_path))

        # handle the case where an event loop is already running
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, _run()).result()
        else:
            asyncio.run(_run())

    # ── duration probe ──────────────────────────────────────────
    @staticmethod
    def get_audio_duration(audio_path: Path) -> float:
        """Get audio duration using ffprobe or ffmpeg -i fallback."""
        import re as _re
        # Try ffprobe first
        try:
            result = subprocess.run(
                [
                    FFPROBE_BIN, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception:
            pass

        # Fallback: parse duration from `ffmpeg -i` stderr
        try:
            from config import FFMPEG_BIN
            result = subprocess.run(
                [FFMPEG_BIN, "-i", str(audio_path), "-f", "null", "-"],
                capture_output=True, text=True,
            )
            match = _re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
            if match:
                h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
                return h * 3600 + m * 60 + s
        except Exception:
            pass

        # Last resort: estimate from file size
        size = audio_path.stat().st_size
        if audio_path.suffix == ".mp3":
            # ~16 kBps for typical edge-tts mp3
            return size / 16000
        return size / (AUDIO_SAMPLE_RATE * 2)
