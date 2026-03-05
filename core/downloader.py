"""
Media Downloader — download photos/videos from URLs to local temp folder.
Handles retries, progress logging, and deduplication.
"""

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import MEDIA_DIR

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 256  # 256 KB
DOWNLOAD_HEADERS = {
    "User-Agent": "AutoVideoEngine/1.0 (https://github.com; bot)"
}


class MediaDownloader:
    """Download media files into the project media/ folder."""

    def __init__(self, dest_dir: Optional[Path] = None):
        self.dest_dir = dest_dir or MEDIA_DIR
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    # ── public ──────────────────────────────────────────────────
    def download(self, url: str, filename: Optional[str] = None, retries: int = 3) -> Path:
        """
        Download *url* and return the local Path.
        If *filename* is None, derive one from the URL hash.
        Skips download if file already exists (content‑addressed).
        """
        if filename is None:
            ext = self._guess_ext(url)
            filename = hashlib.md5(url.encode()).hexdigest() + ext

        dest_path = self.dest_dir / filename

        if dest_path.exists():
            logger.info("Already cached: %s", dest_path.name)
            return dest_path

        logger.info("Downloading %s → %s", url[:80], dest_path.name)

        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, stream=True, timeout=60,
                                    headers=DOWNLOAD_HEADERS)
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(CHUNK_SIZE):
                        f.write(chunk)
                logger.info("Saved %s (%.1f MB)", dest_path.name, dest_path.stat().st_size / 1e6)
                return dest_path
            except Exception as exc:
                logger.warning("Attempt %d/%d failed: %s", attempt, retries, exc)
                if dest_path.exists():
                    dest_path.unlink()
                if attempt == retries:
                    raise

        return dest_path  # unreachable but keeps mypy happy

    def download_for_scene(self, scene: dict, results: list) -> Optional[Path]:
        """
        Given search results for a scene, download a media file.
        Uses scene_id to rotate through results so consecutive scenes
        get different media instead of all picking the first result.
        Updates scene dict in‑place.
        """
        if not results:
            logger.error("No results to download for scene %s", scene.get("scene_id"))
            return None

        scene_id = scene.get("scene_id", 0)
        # Rotate: scene 1 → results[0], scene 2 → results[1], etc.
        start_idx = (scene_id - 1) % len(results)
        ordered = results[start_idx:] + results[:start_idx]

        for item in ordered:
            try:
                path = self.download(item["url"])
                scene["media_file"] = str(path)
                return path
            except Exception as exc:
                logger.warning("Skipping media %s: %s", item.get("id"), exc)
        logger.error("No media could be downloaded for scene %s", scene.get("scene_id"))
        return None

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _guess_ext(url: str) -> str:
        """Guess file extension from URL."""
        url_clean = url.split("?")[0]
        if "." in url_clean.split("/")[-1]:
            return "." + url_clean.split(".")[-1].lower()
        return ".mp4"  # default for Pexels videos

    def clear_cache(self):
        """Remove all downloaded media."""
        if self.dest_dir.exists():
            shutil.rmtree(self.dest_dir)
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Media cache cleared.")
