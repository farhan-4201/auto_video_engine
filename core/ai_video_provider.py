
"""
AI Video Provider — generates cinematic video clips using Runway Gen-4 Turbo.
Supports reference_image anchoring for visual consistency across scenes,
and injects camera_move from scene JSON into every generation prompt.
"""

import base64
import hashlib
import logging
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import RUNWAY_API_KEY, AI_VIDEO_MODEL, MEDIA_DIR, AI_VIDEO_RATIO

logger = logging.getLogger(__name__)

# Camera move → natural-language motion directive for Runway prompt
CAMERA_MOVE_DIRECTIVES = {
    "dolly_in": "camera slowly dollies forward toward the subject",
    "dolly_back": "camera slowly dollies backward, revealing the scene",
    "tracking": "camera tracks laterally alongside the subject in smooth motion",
    "static_wide": "locked-off wide shot, no camera movement",
    "crane_down": "camera cranes downward from above, descending into the scene",
    "push_close": "camera pushes in tight to an extreme close-up",
    "pan_left": "camera pans slowly from right to left across the scene",
    "pan_right": "camera pans slowly from left to right across the scene",
}


class AIVideoProvider:
    """Interface for Runway Gen-4 Turbo API with reference-image consistency."""

    def __init__(self):
        self.api_key = RUNWAY_API_KEY
        self.base_url = "https://api.dev.runwayml.com/v1"
        self._reference_image_b64: Optional[str] = None  # cached anchor frame

    @property
    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        }

    # ── Reference image anchor ─────────────────────────────────
    def set_reference_image(self, image_path: Path):
        """Load a reference frame as base64 to anchor visual consistency."""
        with open(image_path, "rb") as f:
            raw = f.read()
        self._reference_image_b64 = base64.b64encode(raw).decode("utf-8")
        logger.info("Reference image set from %s (%d KB)",
                     image_path.name, len(raw) // 1024)

    def generate_reference_image(self, prompt: str) -> Optional[str]:
        """
        Generate a reference frame via Runway Gen-4 image endpoint.
        Returns the URL of the generated image, or None.
        Use this for scene 1 to establish visual style, then pass to all
        subsequent video calls for consistency.
        """
        if not self.api_key:
            return None
        try:
            payload = {
                "model": AI_VIDEO_MODEL,
                "promptText": f"Single key frame, establishing shot. {prompt}",
                "ratio": "16:9",
                "outputFormat": "png",
            }
            resp = requests.post(f"{self.base_url}/images/generations",
                                 json=payload, headers=self._headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            url = data.get("output", [None])[0] or data.get("url")
            if url:
                logger.info("Reference image generated: %s", url[:80])
                # Download and cache as b64
                img_resp = requests.get(url, timeout=60)
                img_resp.raise_for_status()
                self._reference_image_b64 = base64.b64encode(img_resp.content).decode("utf-8")
            return url
        except Exception as e:
            logger.warning("Reference image generation failed: %s", e)
            return None

    # ── Video generation (Gen-4 Turbo) ─────────────────────────
    def generate(self, prompt: str, scene: Optional[Dict] = None,
                 aspect_ratio: str = "16:9") -> Optional[str]:
        """
        Request a video clip from Runway Gen-4 Turbo.
        Injects camera_move directive + reference_image for consistency.
        Returns the URL of the generated video or None.
        """
        if not self.api_key:
            logger.warning("No Runway API Key. Skipping AI video generation.")
            return None

        # Inject camera move into prompt
        camera_move = (scene or {}).get("camera_move", "static_wide")
        cam_directive = CAMERA_MOVE_DIRECTIVES.get(camera_move, "")
        full_prompt = f"{cam_directive}. {prompt}" if cam_directive else prompt

        logger.info("Generating Gen-4 video: %s…", full_prompt[:80])

        try:
            payload = {
                "model": AI_VIDEO_MODEL,
                "promptText": full_prompt,
                "ratio": aspect_ratio,
                "duration": 5,
                "watermark": False,
            }

            # Attach reference image for visual consistency (if available)
            if self._reference_image_b64:
                payload["referenceImage"] = {
                    "uri": f"data:image/png;base64,{self._reference_image_b64}",
                    "weight": 0.65,
                }

            # 1. Create Task
            response = requests.post(f"{self.base_url}/video/generations",
                                     json=payload, headers=self._headers, timeout=60)
            response.raise_for_status()
            task_id = response.json()["id"]

            # 2. Poll for completion
            max_retries = 60
            for i in range(max_retries):
                time.sleep(10)
                status_resp = requests.get(f"{self.base_url}/tasks/{task_id}",
                                           headers=self._headers, timeout=30)
                status_data = status_resp.json()
                status = status_data.get("status", "UNKNOWN")

                if status == "SUCCEEDED":
                    video_url = status_data["output"][0]
                    logger.info("Gen-4 video ready: %s", video_url[:80])
                    return video_url
                elif status in ("FAILED", "CANCELLED"):
                    logger.error("Gen-4 generation failed: %s",
                                 status_data.get("error", "unknown"))
                    return None

                logger.debug("Gen-4 poll %d/%d — status=%s", i + 1, max_retries, status)

            logger.warning("Gen-4 generation timed out after %d polls.", max_retries)
            return None

        except Exception as e:
            logger.error("Runway Gen-4 error: %s", e)
            return None

    # ── Batch generation for a full scene plan ─────────────────
    def generate_for_scenes(self, scenes: List[Dict]) -> List[Dict]:
        """
        Generate AI video for each scene that should use AI footage.
        Establishes a reference image from scene 1, then passes it to all
        subsequent calls for visual consistency.
        """
        if not self.api_key:
            logger.warning("No Runway API key — skipping all AI video generation.")
            return scenes

        # Generate reference image from scene 1's visual prompt
        if scenes and not self._reference_image_b64:
            first_prompt = scenes[0].get("visual_prompt", "")
            self.generate_reference_image(first_prompt)

        for scene in scenes:
            prompt = scene.get("visual_prompt", "")
            url = self.generate(prompt, scene=scene)
            if url:
                local_path = self.download_ai_clip(url)
                if local_path:
                    scene["ai_video_file"] = str(local_path)
                    scene["ai_video_url"] = url

        return scenes

    # ── Download ───────────────────────────────────────────────
    def download_ai_clip(self, url: str) -> Optional[Path]:
        """Download the generated AI clip to local media cache."""
        try:
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            filename = hashlib.md5(url.encode()).hexdigest() + ".mp4"
            out_path = MEDIA_DIR / filename

            if out_path.exists():
                return out_path

            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("Downloaded AI clip: %s (%.1f MB)",
                         out_path.name, out_path.stat().st_size / 1e6)
            return out_path
        except Exception as e:
            logger.error("Failed to download AI clip: %s", e)
            return None
