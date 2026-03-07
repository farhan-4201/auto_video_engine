import asyncio
import logging
import subprocess
import concurrent.futures
from pathlib import Path
from typing import Optional, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    TEMP_DIR,
    AUDIO_SAMPLE_RATE,
    FFPROBE_BIN,
    EDGE_TTS_VOICE,
)

logger = logging.getLogger(__name__)


class TTSEngine:
    """Text-to-speech engine using edge-tts (free Microsoft neural voices)."""

    def __init__(self, project_id: str = "default"):
        self.output_dir = TEMP_DIR / project_id / "tts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.provider = "edge-tts"

    def set_project(self, project_id: str):
        self.output_dir = TEMP_DIR / project_id / "tts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── public ──────────────────────────────────────────────────
    def synthesize(self, text: str, scene_id: int) -> tuple[Path, List[dict]]:
        """Render text to audio and capture word-level timing."""
        out_path = self.output_dir / f"scene_{scene_id}.mp3"
        # Word timing JSON
        timing_path = self.output_dir / f"scene_{scene_id}_timing.json"

        if out_path.exists() and timing_path.exists():
            import json
            with open(timing_path, "r") as f:
                return out_path, json.load(f)

        audio, timing = self._synthesize_edge(text, out_path)
        
        # Cache timing
        import json
        with open(timing_path, "w") as f:
            json.dump(timing, f)

        return audio, timing

    def synthesize_scenes(self, scene_plan: dict) -> dict:
        """Parallel synthesis of all scenes with word-level timing."""
        logger.info(f"Starting parallel TTS synthesis for {len(scene_plan['scenes'])} scenes...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_scene = {
                executor.submit(self.synthesize, s["narration"], s["scene_id"]): s 
                for s in scene_plan["scenes"]
            }
            
            for future in concurrent.futures.as_completed(future_to_scene):
                scene = future_to_scene[future]
                audio, timing = future.result()
                scene["tts_file"] = str(audio)
                scene["tts_duration"] = self.get_audio_duration(audio)
                scene["word_timing"] = timing
        
        return scene_plan

    # ── implementation ──────────────────────────────────────────
    def _synthesize_edge(self, text: str, out_path: Path) -> tuple[Path, List[dict]]:
        import edge_tts
        
        word_data = []
        async def _run():
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            with open(out_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        try:
                            word_data.append({
                                "word": chunk.get("text", ""),
                                "start": chunk.get("offset", 0) / 10**7,
                                "duration": chunk.get("duration", 0) / 10**7
                            })
                        except Exception:
                            pass
        
        # Handle event loop: thread-safe asyncio.run
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, _run()).result()
        else:
            asyncio.run(_run())
        
        return out_path, word_data

    @staticmethod
    def get_audio_duration(audio_path: Path) -> float:
        """Get audio duration using ffmpeg -i (works with imageio-ffmpeg bundle)."""
        try:
            from config import FFMPEG_BIN
            result = subprocess.run(
                [FFMPEG_BIN, "-i", str(audio_path), "-hide_banner"],
                capture_output=True, text=True, timeout=15
            )
            import re
            dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', result.stderr)
            if dur_match:
                h, m, s = dur_match.groups()
                return int(h) * 3600 + int(m) * 60 + float(s)
            return 5.0  # fallback
        except:
            return 5.0  # fallback
