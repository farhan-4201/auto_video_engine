"""
YouTube Fetcher — replaces pexels_fetcher.py / pixabay_fetcher.py.

Uses yt-dlp to search YouTube and download actual movie clips, trailers,
and scene compilations for the movie being processed.

Install: pip install yt-dlp
"""

import logging
import os
import re
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    MEDIA_DIR, TEMP_DIR,
    YTDLP_MAX_RESULTS, YTDLP_FORMAT,
)

logger = logging.getLogger(__name__)


class YouTubeFetcher:
    """
    Search YouTube for movie clips and download the best match using yt-dlp.

    Usage:
        fetcher = YouTubeFetcher()
        result = fetcher.fetch_for_scene(scene)
        # result["media_file"] → Path to downloaded .mp4
    """

    def __init__(self):
        self._check_ytdlp()
        self.media_dir = MEDIA_DIR
        self.media_dir.mkdir(parents=True, exist_ok=True)

    # ── public ──────────────────────────────────────────────────
    def fetch_for_scene(self, scene: Dict) -> Dict:
        """
        Try each query variant in order until a clip is downloaded.
        Updates scene dict in-place with media_file, yt_video_id, yt_title.
        Returns the updated scene dict.
        """
        scene_id = scene["scene_id"]
        query_variants: List[str] = scene.get("query_variants") or [scene["search_query"]]

        for query in query_variants:
            logger.info("  Scene %d — YouTube search: %s", scene_id, query)
            result = self._search_and_download(query, scene_id)
            if result:
                scene["media_file"] = str(result["filepath"])
                scene["yt_video_id"] = result.get("id")
                scene["yt_title"] = result.get("title")
                logger.info(
                    "  Scene %d — Downloaded: %s",
                    scene_id, result.get("title", "unknown")
                )
                return scene

        logger.warning("  Scene %d — All queries failed, no clip found.", scene_id)
        return scene

    def fetch_all_scenes(self, scene_plan: Dict) -> Dict:
        """Fetch clips for all scenes in the plan. Returns updated plan."""
        logger.info("YouTube fetch starting for %d scenes…", scene_plan["total_scenes"])
        for scene in scene_plan["scenes"]:
            self.fetch_for_scene(scene)
        fetched = sum(1 for s in scene_plan["scenes"] if s.get("media_file"))
        logger.info("YouTube fetch done: %d/%d scenes have clips", fetched, scene_plan["total_scenes"])
        return scene_plan

    # ── core download logic ─────────────────────────────────────
    def _search_and_download(self, query: str, scene_id: int) -> Optional[Dict]:
        """
        Run yt-dlp to search YouTube and download the first usable result.
        Returns dict with filepath, id, title — or None on failure.
        """
        # Sanitize query for use as filename
        safe_query = re.sub(r"[^\w\s-]", "", query).strip()[:60]
        safe_query = re.sub(r"\s+", "_", safe_query)
        output_stem = f"scene_{scene_id:02d}_{safe_query}"
        output_path = self.media_dir / f"{output_stem}.mp4"

        # Skip download if already cached
        if output_path.exists() and output_path.stat().st_size > 100_000:
            logger.info("  Cache hit: %s", output_path.name)
            return {"filepath": output_path, "id": None, "title": output_stem}

        # yt-dlp command:
        # ytsearch3: searches YouTube and tries the top 3 results
        yt_query = f"ytsearch{YTDLP_MAX_RESULTS}:{query}"

        cmd = [
            "yt-dlp",
            yt_query,
            "--format", YTDLP_FORMAT,
            "--output", str(self.media_dir / f"{output_stem}.%(ext)s"),
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--max-downloads", "1",          # stop after first successful download
            "--no-warnings",
            "--quiet",
            "--print-json",                  # print metadata of downloaded video
            "--socket-timeout", "30",
            "--retries", "3",
            # Avoid age-gated or unavailable videos
            "--match-filter", "!is_live & duration < 1800",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Find the downloaded file (yt-dlp may change extension)
            downloaded = self._find_downloaded_file(self.media_dir, output_stem)
            if downloaded and downloaded.exists() and downloaded.stat().st_size > 100_000:
                # Parse metadata from stdout
                meta = self._parse_yt_meta(result.stdout)
                return {
                    "filepath": downloaded,
                    "id": meta.get("id"),
                    "title": meta.get("title", query),
                }
            else:
                if result.stderr:
                    logger.debug("yt-dlp stderr: %s", result.stderr[:300])
                return None

        except subprocess.TimeoutExpired:
            logger.warning("  yt-dlp timed out for query: %s", query)
            return None
        except FileNotFoundError:
            logger.error("yt-dlp not found. Install it: pip install yt-dlp")
            return None
        except Exception as e:
            logger.error("yt-dlp error for '%s': %s", query, e)
            return None

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _find_downloaded_file(directory: Path, stem: str) -> Optional[Path]:
        """Find a file matching the stem with any extension.
        Prefer clean merged files over format-specific partial streams."""
        # First pass: look for clean merged files (no format ID like .f134)
        for ext in [".mp4", ".mkv", ".webm", ".avi", ".mov"]:
            candidate = directory / f"{stem}{ext}"
            if candidate.exists() and candidate.stat().st_size > 100_000:
                return candidate
        # Second pass: broader search, pick largest (may include format-specific files)
        matches = [
            p for p in directory.glob(f"{stem}*")
            if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".avi", ".mov")
            and p.stat().st_size > 100_000
        ]
        if matches:
            return max(matches, key=lambda p: p.stat().st_size)
        return None

    @staticmethod
    def _parse_yt_meta(stdout: str) -> Dict:
        """Parse the last JSON line from yt-dlp --print-json output."""
        meta = {}
        for line in reversed(stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    meta = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
        return meta

    @staticmethod
    def _check_ytdlp():
        """Warn if yt-dlp is not installed."""
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info("yt-dlp version: %s", result.stdout.strip())
        else:
            logger.warning(
                "yt-dlp not found or not working. Install: pip install yt-dlp\n"
                "Also recommended: pip install yt-dlp[default]"
            )