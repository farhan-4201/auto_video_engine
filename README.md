# Auto Video Engine

**Zero‑cost, fully‑local YouTube video generator.**  
Feed it a topic and a style → get a narrated, subtitled 1080p MP4.

---

## Pipeline

```
Input (topic + style)
        ↓
Script Template (local JSON)
        ↓
Scene JSON (keywords, timing)
        ↓
Pexels API (free stock media) / Pixabay (fallback)
        ↓
Download to local cache
        ↓
Coqui TTS (local neural voice)
        ↓
FFmpeg scene assembly
        ↓
SRT subtitles from TTS timing
        ↓
Final 1080p MP4
```

---

## Folder Structure

```
auto_video_engine/
├── main.py                  # CLI entry‑point & orchestrator
├── config.py                # all paths, keys, defaults
├── requirements.txt
├── README.md
│
├── core/                    # pipeline modules
│   ├── __init__.py
│   ├── script_writer.py     # topic+style → narration script
│   ├── scene_builder.py     # script → scene JSON with keywords
│   ├── pexels_fetcher.py    # Pexels API search (free)
│   ├── pixabay_fetcher.py   # Pixabay API search (free, recommended)
│   ├── media_provider.py    # auto‑selects provider with fallback
│   ├── downloader.py        # download & cache media files
│   ├── tts_engine.py        # Coqui TTS / pyttsx3 fallback
│   ├── ffmpeg_assembler.py  # scene clips + concatenation
│   ├── subtitle_gen.py      # SRT generation from timing
│   └── compositor.py        # burn subs + mix music → final
│
├── templates/               # data‑driven templates
│   ├── script_templates.json
│   └── media_search_hints.json
│
├── assets/
│   ├── fonts/               # custom subtitle fonts (optional)
│   └── music/               # background music MP3s (optional)
│
├── media/                   # downloaded stock media cache
├── temp/                    # intermediate clips, TTS, SRT
└── output/                  # finished videos land here
```

---

## Quick Start

### 1. Prerequisites

| Tool | Install |
|------|---------|
| **Python 3.9+** | https://python.org |
| **FFmpeg** | `choco install ffmpeg` (Win) · `brew install ffmpeg` (Mac) · `apt install ffmpeg` (Linux) |
| **Pixabay API key** | Free at https://pixabay.com/api/docs/ (recommended) |
| **Pexels API key** | Free at https://www.pexels.com/api/ (alternative) |

### 2. Install

```bash
cd auto_video_engine
pip install -r requirements.txt
```

### 3. Configure

Set your API key — only **one** provider is needed (pick one):

```bash
# OPTION A: Pixabay (recommended — more reliable)
set PIXABAY_API_KEY=your_key_here          # Windows CMD
$env:PIXABAY_API_KEY="your_key_here"       # PowerShell
export PIXABAY_API_KEY=your_key_here       # Linux/Mac

# OPTION B: Pexels
set PEXELS_API_KEY=your_key_here           # Windows CMD
$env:PEXELS_API_KEY="your_key_here"        # PowerShell
export PEXELS_API_KEY=your_key_here        # Linux/Mac

# OR edit config.py directly
PIXABAY_API_KEY = "your_key_here"
# Both can be set for auto-fallback
```

### 4. Run

```bash
# documentary about black holes
python main.py "Black Holes" --style documentary

# motivational video about discipline
python main.py "Self Discipline" --style motivational

# with background music
python main.py "Artificial Intelligence" --style cinematic --music assets/music/ambient.mp3

# force a specific media provider
python main.py "Ocean Life" --style documentary --provider pixabay
```

### 5. Output

Your finished video appears in `output/<topic>_final.mp4`.

---

## Style Presets

| Style | Voice | Media | Mood |
|-------|-------|-------|------|
| `documentary` | Normal pace | Nature/science footage | Informative |
| `motivational` | Slightly slower | Inspirational clips | Uplifting |
| `educational` | Normal pace | Clean diagrams/photos | Academic |
| `cinematic` | Slow, dramatic | Moody landscapes | Epic |

---

## FFmpeg Command Templates Used

### Still image → scene clip (Ken Burns zoom)
```
ffmpeg -y -loop 1 -i IMAGE -i AUDIO
  -vf "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':
       y='ih/2-(ih/zoom/2)':d=FRAMES:s=1920x1080:fps=30"
  -t DURATION -c:v libx264 -pix_fmt yuv420p -c:a aac OUTPUT
```

### Stock video → scene clip (scale + crop)
```
ffmpeg -y -i VIDEO -i AUDIO
  -vf "scale=1920:1080:force_original_aspect_ratio=increase,
       crop=1920:1080"
  -t DURATION -map 0:v:0 -map 1:a:0
  -c:v libx264 -c:a aac OUTPUT
```

### Concatenate all clips
```
ffmpeg -y -f concat -safe 0 -i filelist.txt
  -c:v libx264 -b:v 5M -c:a aac -b:a 192k
  -movflags +faststart OUTPUT
```

### Burn SRT subtitles
```
ffmpeg -y -i VIDEO
  -vf "subtitles='SRTFILE':force_style='FontSize=24,
       PrimaryColour=&HFFFFFF&,BorderStyle=3,MarginV=40'"
  -c:v libx264 -c:a copy OUTPUT
```

### Mix background music
```
ffmpeg -y -i VIDEO -stream_loop -1 -i MUSIC
  -filter_complex "[1:a]volume=0.08,afade=t=out:st=0:d=3[bg];
                    [0:a][bg]amix=inputs=2:duration=first[aout]"
  -map 0:v -map "[aout]" -c:v copy -c:a aac -shortest OUTPUT
```

---

## Extending

- **Add new styles**: edit `templates/script_templates.json` + `media_search_hints.json` + add a preset in `config.py`
- **Swap TTS engine**: subclass or replace `core/tts_engine.py` — it already has a pyttsx3 fallback
- **Add AI scripts**: replace `ScriptWriter` with an LLM call (OpenAI / local Ollama) for dynamic narration
- **Add transitions**: extend `FFmpegAssembler` with xfade filters between clips

---

## License

Free for personal use. Pexels media is royalty‑free under the [Pexels License](https://www.pexels.com/license/).
