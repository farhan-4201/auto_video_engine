<div align="center">

# 🎬 Auto Video Engine

### AI-Powered Movie Video Generation Pipeline

**Feed it a movie title → get a fully narrated, subtitled, cinematic 1080p MP4.**

Zero cost. Fully automated. Production quality.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-powered-green.svg?style=flat-square&logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg?style=flat-square)](LICENSE)

---

https://github.com/user-attachments/assets/7551c368-a7fd-4f3f-a3d9-31edaa88a71b



</div>

## Output Demo — *Dirty Harry (1971)*

> Generated end-to-end by this pipeline: script → clips → narration → subtitles → final composite.

https://github.com/user-attachments/assets/dirty-harry-demo.mp4

<!-- ⬆️ To add the video: open a GitHub issue, drag-and-drop output/dirty harry.mp4,
     copy the generated URL, and replace the placeholder above. -->

<p align="center">
  <code>python main.py "Dirty Harry" --style cinematic</code> → <code>output/dirty harry.mp4</code>
</p>

<details>
<summary><b>🎥 More sample outputs</b></summary>

| Movie | Style | Command |
|-------|-------|---------|
| **The Dark Knight** | `cinematic` | `python main.py "The Dark Knight" --style cinematic` |
| **Inception** | `cinematic` | `python main.py "Inception" --style cinematic` |
| **Black Holes** | `documentary` | `python main.py "Black Holes" --style documentary` |
| **Harry Potter** | `cinematic` | `python main.py "Harry Potter" --style cinematic` |
| **The Future of Humanity** | `documentary` | `python main.py "The Future of Humanity" --style documentary` |

</details>

---

## Why This Project Exists

Most "AI video generators" are thin wrappers around a single API. This is a **complete production pipeline** — script generation, media sourcing, speech synthesis, cinematic post-processing, and final composition — built from scratch with zero paid dependencies.

**Key engineering decisions:**
- **Gemini API (free tier)** for movie-aware script generation with real character/plot knowledge
- **yt-dlp** for sourcing actual movie clips from YouTube (no API key)
- **edge-tts** for neural narration with word-level timing at 100 nanosecond precision
- **FFmpeg filter graphs** for cinematic color grading (Kodak 2383 curves), Ken Burns motion, peak-event effects, and sidechain-ducked music mixing
- **ASS subtitle format** with per-word highlight animation synced to TTS timestamps

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        VIDEO ORCHESTRATOR                         │
│                          (main.py)                                │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────────┤
│  Stage 1 │  Stage 2 │  Stage 3 │  Stage 4 │  Stage 5 │  Stage 6  │
│  Script  │  Scene   │  Media   │   TTS    │ Assembly │  Final    │
│  Writer  │  Builder │  Fetch   │  Engine  │  FFmpeg  │ Composite │
├──────────┼──────────┼──────────┼──────────┼──────────┼───────────┤
│ Gemini   │ Query    │ yt-dlp   │ edge-tts │ Kodak    │ Burn ASS  │
│ API      │ variants │ search + │ word-    │ 2383 LUT │ subtitles │
│ (free)   │ + fall-  │ download │ boundary │ Ken Burns│ Mix music │
│          │ backs    │          │ timing   │ FX peaks │ Ducking   │
└──────────┴──────────┴──────────┴──────────┴──────────┴───────────┘
                                    │
                              REST API (FastAPI)
                              POST /api/v1/videos
                              GET  /api/v1/videos/{id}
                              GET  /api/v1/health
```

### Data Flow

```
Topic + Style
      ↓
Gemini → structured JSON script (real characters, scenes, themes)
      ↓
SceneBuilder → enriched scene plan with ranked YouTube search queries
      ↓
yt-dlp → download actual movie clips/trailers (query variant fallbacks)
      ↓
edge-tts → MP3 narration + word-level timing JSON (100ns precision)
      ↓
FFmpegAssembler → per-scene clips with:
  • Cinematic color grading (Kodak 2383 film curves)
  • Emotion-driven Ken Burns camera motion
  • Peak-event visual effects (zoom punch, flash frame)
  • Film grain + vignette texture
      ↓
SubtitleGenerator → ASS format with word-by-word cyan highlight animation
      ↓
Compositor → burn subtitles + mix background music with:
  • Per-scene volume automation (swell_up / swell_down / silence / hold)
  • Sidechain ducking via FFmpeg anequalizer + sidechaingate
      ↓
Final 1080p MP4
```

---

## Project Structure

```
auto_video_engine/
│
├── main.py                      # CLI entry-point & pipeline orchestrator
├── api.py                       # FastAPI REST API (async job queue)
├── schemas.py                   # Pydantic models for request/response validation
├── config.py                    # All paths, API keys, style presets, defaults
├── Dockerfile                   # Production container image
├── docker-compose.yml           # One-command deployment
├── .env.example                 # Environment variable template
├── .github/workflows/ci.yml     # CI pipeline (lint → test → Docker build)
│
├── core/                        # Pipeline modules
│   ├── script_writer.py         # Gemini-powered movie script generation
│   ├── scene_builder.py         # Script → Scene plan with YouTube search queries
│   ├── youtube_fetcher.py       # yt-dlp search + download (no API key)
│   ├── media_provider.py        # Unified provider with auto-fallback chain
│   ├── wikimedia_fetcher.py     # Wikimedia Commons (royalty-free, no key)
│   ├── pixabay_fetcher.py       # Pixabay API (free tier)
│   ├── downloader.py            # Content-addressed download cache
│   ├── tts_engine.py            # edge-tts with word-level WordBoundary timing
│   ├── ffmpeg_assembler.py      # Cinematic scene assembly (500+ lines)
│   ├── subtitle_gen.py          # ASS subtitle generation with word animation
│   ├── compositor.py            # Final composition (subs + music + effects)
│   ├── peak_detector.py         # Power-word → visual effect mapping
│   ├── audio_assets_provider.py # Emotion-aware background music selection
│   └── ai_video_provider.py     # Runway Gen-4 Turbo (optional)
│
├── templates/                   # Data-driven generation templates
│   ├── script_templates.json    # Style-specific narration structures
│   ├── media_search_hints.json  # Per-style search keyword guidance
│   └── example_custom_script.json
│
├── scripts/                     # Pre-written script examples
│   └── dirty_harry_explained.json
│
├── assets/
│   ├── fonts/                   # Custom subtitle fonts
│   ├── music/                   # Background music MP3s
│   └── sfx/                     # Sound effects
│
├── media/                       # Downloaded media cache (content-addressed)
├── temp/                        # Intermediate build artifacts (per-project)
└── output/                      # Finished videos
```

---

## Quick Start

### Prerequisites

| Dependency | Required | Install |
|------------|----------|---------|
| **Python 3.11+** | Yes | [python.org](https://python.org) |
| **FFmpeg** | Yes | `choco install ffmpeg` · `brew install ffmpeg` · `apt install ffmpeg` |
| **Gemini API key** | Free | [aistudio.google.com](https://aistudio.google.com/app/apikey) |

### Option A: Local Install

```bash
git clone https://github.com/YOUR_USERNAME/auto-video-engine.git
cd auto-video-engine

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Gemini API key

# Generate a video
python main.py "Dirty Harry" --style cinematic
```

### Option B: Docker

```bash
# Clone and configure
git clone https://github.com/YOUR_USERNAME/auto-video-engine.git
cd auto-video-engine
cp .env.example .env      # add your API keys

# Build and run
docker compose up --build

# The API is now at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Option C: REST API

```bash
# Start the API server
uvicorn api:app --reload --port 8000

# Submit a video generation job
curl -X POST http://localhost:8000/api/v1/videos \
  -H "Content-Type: application/json" \
  -d '{"topic": "Dirty Harry", "style": "cinematic"}'

# Check job status
curl http://localhost:8000/api/v1/videos/{job_id}

# Download finished video
curl -O http://localhost:8000/api/v1/videos/{job_id}/download
```

---

## REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/videos` | Queue a new video generation job |
| `GET` | `/api/v1/videos` | List all jobs (most recent first) |
| `GET` | `/api/v1/videos/{job_id}` | Get job status, progress, output path |
| `GET` | `/api/v1/videos/{job_id}/download` | Download the finished MP4 |
| `DELETE` | `/api/v1/videos/{job_id}` | Remove a job from the registry |
| `GET` | `/api/v1/styles` | List available style presets |
| `POST` | `/api/v1/preview-script` | Dry-run: generate script only (no video) |
| `GET` | `/api/v1/health` | Dependency health check |

**Interactive docs:** `http://localhost:8000/docs` (Swagger UI)

<details>
<summary><b>Example: POST /api/v1/videos</b></summary>

**Request:**
```json
{
  "topic": "Dirty Harry 1971",
  "style": "cinematic",
  "music": null,
  "script_path": null
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "a3f8b2c1d4e5",
  "topic": "Dirty Harry 1971",
  "style": "cinematic",
  "status": "queued",
  "progress": 0,
  "current_step": "",
  "output_path": null,
  "error": null,
  "created_at": "2026-03-06T12:00:00+00:00",
  "duration_secs": null
}
```

</details>

---

## Style Presets

| Style | Voice Pacing | Color Grade | Mood | Music Volume |
|-------|-------------|-------------|------|-------------|
| `documentary` | Normal (1.0x) | Muted film | Informative | 8% |
| `motivational` | Slower (0.95x) | Vintage curves | Uplifting | 12% |
| `educational` | Normal (1.0x) | Clean/neutral | Academic | 5% |
| `cinematic` | Slow (0.9x) | Kodak 2383 teal-orange | Epic | 10% |
| `review` | Normal (1.0x) | Neutral | Analytical | 8% |

---

## Technical Deep Dive

### Cinematic Color Grading

Every scene passes through a **Kodak 2383 print-film emulation** built as FFmpeg curves:

```
curves=r='0/0.05 0.15/0.12 0.35/0.33 0.65/0.68 0.85/0.82 1/0.92':
      g='0/0.04 0.15/0.13 0.35/0.32 0.65/0.65 0.85/0.80 1/0.90':
      b='0/0.08 0.15/0.16 0.35/0.36 0.65/0.62 0.85/0.76 1/0.86'
```

Then scene-specific grades are layered on top:

| Grade | Effect | When |
|-------|--------|------|
| `cold_desaturated` | Blue shadows, muted color | Dread, mystery |
| `warm_golden` | Amber highlights, lifted blacks | Triumph, nostalgia |
| `teal_orange` | Hollywood blockbuster look | Action, epic |
| `high_contrast` | Crushed blacks, sharp detail | Tension, thriller |
| `muted_film` | Gentle desaturation | Documentary, neutral |

### Emotion-Driven Ken Burns Motion

Camera motion is automatically mapped from scene emotion metadata:

| Emotion | Camera Behavior |
|---------|----------------|
| `dread` | Slow zoom **out** (pull back, reveal emptiness) |
| `epic` / `triumph` | Slow zoom **in** (push toward subject) |
| `mystery` | Slow lateral pan (searching, uncertain) |
| `tension` | Subtle handheld shake (randomized offset) |
| `sorrow` | Static with slight downward drift |

### Peak-Event Visual Effects

The `PeakDetector` scans TTS word timings for emotionally charged "power words" (100+ curated terms) and generates frame-accurate visual effects:

- **zoom_punch** — 3-frame scale burst (1.0→1.04→1.0) at the exact word timestamp
- **flash_frame** — 2-frame white flash overlay
- **hard_cut** — abrupt cut (handled at concat level)

Effect selection is weighted by scene emotion (e.g. `dread` favors hard cuts, `epic` favors zoom punches).

### Word-Level Subtitle Animation

Subtitles use the **ASS (Advanced SubStation Alpha)** format with word-by-word highlighting:

```
Dialogue: 0,0:00:02.45,0:00:04.12,Default,,0,0,0,,Released in 1971 {\c&H00FFFF&}Dirty{\c&HFFFFFF&}
```

Words are grouped into 3–4 word phrases. The current word highlights in **cyan** (`&H00FFFF&`), synced to edge-tts WordBoundary events captured at 100-nanosecond precision.

### Music Mixing with Sidechain Ducking

Background music is mixed with **per-scene volume automation** driven by `music_cue` metadata:

| Cue | Behavior |
|-----|----------|
| `swell_up` | Fade 0.3→0.8 over 1.5s at scene start |
| `swell_down` | Fade 0.8→0.2 over last 1.0s of scene |
| `silence` | Drop to 5% for entire scene |
| `hold` | Maintain base level |

Plus **sidechain ducking** via FFmpeg's `anequalizer` + `sidechaingate` filters — music automatically dips when narration is detected.

---

## Scene Metadata Schema

Every scene carries rich cinematic metadata that flows through the entire pipeline:

```json
{
  "scene_id": 1,
  "narration": "Released in 1971, Dirty Harry introduced one of the toughest cops in movie history.",
  "search_query": "Dirty Harry 1971 opening San Francisco skyline",
  "clip_type": "trailer",
  "emotion": "epic",
  "intensity": 0.8,
  "camera_move": "dolly_in",
  "color_grade": "cold_desaturated",
  "music_cue": "swell_up",
  "cut_style": "fade_black"
}
```

---

## Design Decisions

| Decision | Why |
|----------|-----|
| **Project isolation** (`temp/{project_id}/`) | Enables parallel generation — each run is fully independent |
| **Content-addressed caching** | TTS, media, normalized clips are cached by content hash — re-runs skip completed work |
| **Query variant fallbacks** | Scene plan includes 3–5 ranked YouTube queries — fetcher tries each until success |
| **Metadata passthrough** | Cinematic fields (emotion, color_grade, camera_move) flow unchanged from script → final render |
| **FFmpeg as subprocess** | Commands built as Python lists — reproducible, debuggable, no library bindings |
| **Pydantic validation** | All API input/output validated at the boundary — invalid requests fail fast |
| **Background job queue** | Long-running renders execute in threads — API returns immediately with job ID |

---

## Extending

| Extension | How |
|-----------|-----|
| **Add new styles** | Add preset to `STYLE_PRESETS` in `config.py` + template in `templates/` |
| **Custom script** | Write a JSON file matching the scene schema → `python main.py --script your_script.json` |
| **Swap TTS engine** | Subclass `TTSEngine` — edge-tts, OpenAI TTS, ElevenLabs are all supported |
| **Add AI-generated footage** | Configure `RUNWAY_API_KEY` in `.env` → `AIVideoProvider` generates clips via Runway Gen-4 Turbo |
| **Add transitions** | Extend `FFmpegAssembler` with xfade filters between clips |
| **Deploy to cloud** | `docker compose up` — API + health checks ready for AWS/GCP/Fly.io |

---

## CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push:

1. **Lint** — `ruff check .`
2. **Test** — `pytest tests/ -v`
3. **Docker** — Build image + verify `/api/v1/health` endpoint responds

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11+ |
| **API** | FastAPI + Uvicorn |
| **Validation** | Pydantic v2 |
| **Script AI** | Google Gemini API (free tier) |
| **Media** | yt-dlp (YouTube) · Wikimedia Commons · Pixabay |
| **TTS** | edge-tts (Microsoft neural voices, free) |
| **Video** | FFmpeg (subprocess, filter graphs) |
| **AI Video** | Runway Gen-4 Turbo (optional) |
| **Container** | Docker + docker-compose |
| **CI** | GitHub Actions |

---

## License

MIT License. Media sourced via yt-dlp is subject to YouTube's Terms of Service. Wikimedia Commons media is freely licensed (CC / public domain). Pixabay media is royalty-free under the [Pixabay License](https://pixabay.com/service/license-summary/).
