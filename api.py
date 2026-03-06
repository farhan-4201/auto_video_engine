"""
FastAPI REST API — exposes the video generation pipeline as a web service.

Endpoints:
    POST   /api/v1/videos          → Queue a new video generation job
    GET    /api/v1/videos           → List all jobs
    GET    /api/v1/videos/{job_id}  → Get job status & progress
    DELETE /api/v1/videos/{job_id}  → Cancel a running job
    GET    /api/v1/styles           → List available style presets
    GET    /api/v1/health           → Dependency health check
    POST   /api/v1/preview-script   → Dry-run: generate script without video
"""

import logging
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import (
    FFMPEG_BIN,
    GEMINI_API_KEY,
    OUTPUT_DIR,
    STYLE_PRESETS,
)
from schemas import (
    HealthResponse,
    JobStatus,
    StylePreset,
    VideoJob,
    VideoRequest,
)

logger = logging.getLogger(__name__)

# ── In-memory job store (swap for Redis/Postgres in prod) ──────
_jobs: Dict[str, VideoJob] = {}
_job_lock = threading.Lock()


# ── Lifespan ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Auto Video Engine API starting…")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Auto Video Engine API shutting down.")


# ── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="Auto Video Engine",
    description="Zero-cost AI-powered movie video generation pipeline.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Worker ─────────────────────────────────────────────────────
def _run_pipeline(job_id: str, topic: str, style: str, music: str | None, script_path: str | None):
    """Execute the full pipeline in a background thread."""
    from main import VideoOrchestrator

    def _update(step: str, progress: int):
        with _job_lock:
            _jobs[job_id].current_step = step
            _jobs[job_id].progress = progress
            _jobs[job_id].status = JobStatus.running

    try:
        _update("Initialising pipeline", 5)
        orch = VideoOrchestrator()

        _update("Generating script", 15)
        final = orch.run(
            topic=topic,
            style=style,
            bg_music=music,
            script_path=script_path,
        )

        with _job_lock:
            _jobs[job_id].status = JobStatus.completed
            _jobs[job_id].progress = 100
            _jobs[job_id].current_step = "Done"
            _jobs[job_id].output_path = str(final)
            start = datetime.fromisoformat(_jobs[job_id].created_at)
            _jobs[job_id].duration_secs = round(
                (datetime.now(timezone.utc) - start).total_seconds(), 1
            )

    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        with _job_lock:
            _jobs[job_id].status = JobStatus.failed
            _jobs[job_id].error = str(exc)


# ── Routes ─────────────────────────────────────────────────────
@app.post("/api/v1/videos", response_model=VideoJob, status_code=status.HTTP_202_ACCEPTED)
def create_video(req: VideoRequest):
    """Queue a new video generation job."""
    job_id = uuid.uuid4().hex[:12]
    job = VideoJob(
        job_id=job_id,
        topic=req.topic,
        style=req.style.value,
        status=JobStatus.queued,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _job_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_pipeline,
        args=(job_id, req.topic, req.style.value, req.music, req.script_path),
        daemon=True,
    )
    thread.start()
    return job


@app.get("/api/v1/videos", response_model=list[VideoJob])
def list_videos():
    """List all jobs (most recent first)."""
    with _job_lock:
        return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


@app.get("/api/v1/videos/{job_id}", response_model=VideoJob)
def get_video(job_id: str):
    """Get job status and progress."""
    with _job_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/v1/videos/{job_id}/download")
def download_video(job_id: str):
    """Download the finished MP4 file."""
    with _job_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.completed or not job.output_path:
        raise HTTPException(status_code=409, detail="Video not ready yet")
    path = Path(job.output_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.delete("/api/v1/videos/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(job_id: str):
    """Remove a job from the registry."""
    with _job_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        del _jobs[job_id]


@app.get("/api/v1/styles")
def list_styles():
    """List available style presets with their configuration."""
    return {name: preset for name, preset in STYLE_PRESETS.items()}


@app.post("/api/v1/preview-script")
def preview_script(req: VideoRequest):
    """Dry-run: generate only the script JSON (no video rendering)."""
    from core.script_writer import ScriptWriter
    from core.scene_builder import SceneBuilder

    writer = ScriptWriter()
    script = writer.generate(req.topic, req.style.value)
    builder = SceneBuilder()
    plan = builder.build(script)
    return plan


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """Check availability of all external dependencies."""

    def _check_cmd(cmd: list[str]) -> bool:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    def _check_edge_tts() -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    return HealthResponse(
        version="2.0.0",
        ffmpeg=_check_cmd([FFMPEG_BIN, "-version"]),
        ytdlp=_check_cmd(["yt-dlp", "--version"]),
        gemini=bool(GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE"),
        edge_tts=_check_edge_tts(),
    )
