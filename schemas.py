"""
Pydantic models for request/response validation across the API and pipeline.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ──────────────────────────────────────────────────────
class StylePreset(str, Enum):
    documentary = "documentary"
    motivational = "motivational"
    educational = "educational"
    cinematic = "cinematic"
    review = "review"


class Emotion(str, Enum):
    epic = "epic"
    mystery = "mystery"
    sorrow = "sorrow"
    triumph = "triumph"
    tension = "tension"
    dread = "dread"


class ClipType(str, Enum):
    trailer = "trailer"
    scene = "scene"
    featurette = "featurette"
    review = "review"
    breakdown = "breakdown"


class MusicCue(str, Enum):
    swell_up = "swell_up"
    swell_down = "swell_down"
    silence = "silence"
    hold = "hold"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


# ── Scene Models ───────────────────────────────────────────────
class SceneInput(BaseModel):
    scene_id: int = Field(ge=1)
    narration: str = Field(min_length=1)
    search_query: str = Field(min_length=1)
    clip_type: ClipType = ClipType.scene
    emotion: Emotion = Emotion.epic
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    pacing: str = "medium"
    camera_move: str = "static_wide"
    color_grade: str = "muted_film"
    music_cue: MusicCue = MusicCue.hold
    estimated_duration: float = Field(default=8.0, ge=1.0, le=30.0)


class SceneOutput(BaseModel):
    scene_id: int
    narration: str
    search_query: str
    clip_type: str
    emotion: str
    media_file: Optional[str] = None
    tts_file: Optional[str] = None
    tts_duration: Optional[float] = None


# ── Job Models ─────────────────────────────────────────────────
class VideoRequest(BaseModel):
    """POST body for /api/v1/videos — start a new video generation job."""
    topic: str = Field(min_length=1, max_length=200, examples=["Dirty Harry 1971"])
    style: StylePreset = StylePreset.cinematic
    music: Optional[str] = Field(default=None, description="Path to background music MP3")
    script_path: Optional[str] = Field(default=None, description="Path to custom script JSON")

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, v: str) -> str:
        return v.strip()


class VideoJob(BaseModel):
    """Represents a queued / in-progress / completed video generation job."""
    job_id: str
    topic: str
    style: str
    status: JobStatus = JobStatus.queued
    progress: int = Field(default=0, ge=0, le=100)
    current_step: str = ""
    output_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""
    duration_secs: Optional[float] = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    ffmpeg: bool
    ytdlp: bool
    gemini: bool
    edge_tts: bool


class ScriptTemplateResponse(BaseModel):
    topic: str
    style: str
    director: Optional[str] = None
    year: Optional[str] = None
    total_scenes: int
    scenes: List[SceneOutput]
