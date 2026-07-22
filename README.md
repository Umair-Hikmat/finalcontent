# 🎬 AI Quiz Studio

![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)

A **Canva + Typito style quiz video maker** built entirely with Streamlit, MoviePy,
Pillow, and FFmpeg. Create quiz videos with animated intros, timed countdowns,
answer reveals, fun facts, and outros — export directly to **1080x1920 Shorts**
or **1920x1080 YouTube** format.

## ✨ Features

- **Quiz creator** — title, subtitle, unlimited questions, 4 options each, correct
  answer selection, fun facts, and per-question images.
- **Multiple complete video templates** — Neon Pulse, Classic Trivia, Minimal Clean,
  Retro Arcade (JSON-defined, easy to add more).
- **Animated backgrounds** — solid, animated gradient, particles, static image,
  looped MP4, looped GIF.
- **Font manager** — pulls any Google Font on demand (cached locally) or use your
  own uploaded `.ttf` / `.otf`.
- **Scene timeline** — Intro → Question → Timer → Answer Reveal → Fun Fact → Outro,
  repeated per question, visualized as a proportional timeline strip.
- **7 animation styles** — Fade, Zoom, Slide, Bounce, Glitch, Typewriter, Glow —
  configurable per scene type.
- **Audio** — background music (looped + volume), timed sound effects (timer tick,
  correct reveal, fun-fact chime), optional voiceover track.
- **Rendering** — MoviePy + Pillow + FFmpeg pipeline, disk/memory caching for fast
  iterative previews, progress callback in the UI.
- **JSON project system** — every project and every template is a portable JSON
  file (Pydantic models under the hood).

## 📁 Project structure

```
AI_Quiz_Studio/
├── app.py                     # Streamlit dashboard (entrypoint)
├── requirements.txt
├── Dockerfile                 # Cloud Run compatible
├── config/
│   └── settings.py            # Central paths & defaults
├── core/
│   ├── models.py               # Pydantic models (Project, Quiz, Question, ...)
│   ├── project_manager.py      # JSON save/load/list/delete
│   └── cache.py                 # Memory + disk caching helpers
├── editor/
│   ├── font_manager.py         # Google Fonts fetch/cache + custom TTF
│   ├── timeline.py              # Scene timeline visualizer
│   └── ui_components.py        # Reusable Streamlit widgets
├── engines/
│   ├── animations.py            # Fade/Zoom/Slide/Bounce/Glitch/Typewriter/Glow math
│   ├── background_engine.py     # Gradient/particles/image/video/gif backgrounds
│   ├── audio_engine.py          # Music + SFX composition
│   └── render_engine.py         # Scene scheduling + Pillow frame drawing + MoviePy export
├── templates/
│   ├── template_loader.py       # Load/apply/save JSON templates
│   └── library/                 # neon_pulse.json, classic_trivia.json, ...
├── assets/                      # fonts / images / backgrounds / audio (user uploads land here)
├── data/
│   ├── projects/                # Saved project JSON files
│   └── exports/                 # Rendered MP4 output
└── utils/
    ├── helpers.py                # Color/easing/formatting helpers
    └── validators.py             # Upload + quiz-content validation
```

## 📤 Push this project to GitHub

You already have the full project on disk. To put it on GitHub:

```bash
cd AI_Quiz_Studio
git init
git add .
git commit -m "Initial commit: AI Quiz Studio"
git branch -M main

# Create the repo on GitHub first (via github.com or `gh repo create`), then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Or with the GitHub CLI end-to-end:

```bash
gh repo create YOUR_USERNAME/YOUR_REPO --public --source=. --remote=origin --push
```

After pushing, update the CI badge URL near the top of this README with your
actual `YOUR_USERNAME/YOUR_REPO`.

**What's already wired up for you in `.github/workflows/`:**

- `ci.yml` — runs on every push/PR to `main`: installs deps, byte-compiles every
  module, runs an import + smoke test (builds a tiny in-memory quiz and checks
  the scene schedule), and does a `docker build` to catch Dockerfile regressions.
- `deploy-cloudrun.yml` — manual-trigger workflow (Actions tab → **Run workflow**)
  that builds the image, pushes it to `gcr.io`, and deploys to Cloud Run. To use it,
  add these repo secrets under **Settings → Secrets and variables → Actions**:
  - `GCP_PROJECT_ID` — your Google Cloud project id
  - `GCP_SA_KEY` — a service account key JSON with Cloud Run Admin + Storage Admin
    + Service Account User roles (or switch the `auth` step to Workload Identity
    Federation, which avoids storing a long-lived key)

If you'd rather deploy from your own machine instead of CI, skip straight to the
`gcloud builds submit` / `gcloud run deploy` commands further down.

### Repo hygiene already set up

- `.gitignore` excludes rendered exports, saved project JSON, downloaded fonts,
  and virtualenvs, so the repo stays small — only code + the 4 starter templates
  are tracked.
- `data/projects/`, `data/exports/`, and `assets/fonts/` ship with `.gitkeep`
  placeholders so the folder structure survives even though their contents are
  git-ignored.
- `LICENSE` (MIT) is included at the repo root.

## 🚀 Run locally

```bash
git clone <your-repo-url>
cd AI_Quiz_Studio
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# FFmpeg must be installed and on PATH (imageio-ffmpeg vendors a binary,
# but a system install is recommended for speed):
#   macOS:   brew install ffmpeg
#   Ubuntu:  sudo apt-get install ffmpeg
#   Windows: https://ffmpeg.org/download.html

streamlit run app.py
```

Open http://localhost:8501

## 🐳 Run with Docker

```bash
docker build -t ai-quiz-studio .
docker run -p 8080:8080 ai-quiz-studio
```

## ☁️ Deploy to Google Cloud Run

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-quiz-studio
gcloud run deploy ai-quiz-studio \
  --image gcr.io/YOUR_PROJECT_ID/ai-quiz-studio \
  --platform managed \
  --region YOUR_REGION \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --allow-unauthenticated
```

Notes for Cloud Run:
- The container listens on `$PORT` (defaults to 8080) as required by Cloud Run.
- Video rendering is CPU/memory intensive — allocate at least 2 vCPU / 2Gi RAM,
  and raise `--timeout` for longer quizzes.
- The filesystem is ephemeral: rendered exports and uploaded assets won't persist
  across container restarts/instances. For production use, wire `data/exports`
  and `assets/` to a bucket (e.g. GCS via `gcsfuse`) or object storage of choice.

## 🧩 Adding a new template

Drop a new JSON file into `templates/library/`, e.g. `templates/library/space_odyssey.json`:

```json
{
  "id": "space_odyssey",
  "name": "Space Odyssey",
  "description": "Deep space gradient with slow-drifting stars.",
  "background": { "type": "particles", "color_start": "#000428", "color_end": "#004e92",
                   "particle_count": 90, "particle_color": "#FFFFFF" },
  "font": { "family": "Orbitron", "source": "google", "size": 60, "color": "#FFFFFF" },
  "timing": { "intro": 3, "question": 4, "timer": 5, "answer_reveal": 3, "fun_fact": 4, "outro": 3 },
  "render": { "format": "shorts", "fps": 30, "quality": "high" },
  "animations": {
    "intro": {"type": "zoom", "duration": 0.8, "intensity": 1.0}
  }
}
```

It will automatically appear in the **Templates** tab of the dashboard.

## 🛠️ Tech stack

- **Streamlit** — dashboard UI
- **Pydantic v2** — typed data models & JSON (de)serialization
- **Pillow** — per-frame drawing (text, cards, timers, glow, particles)
- **MoviePy** — clip composition, audio mixing, final MP4 encode via FFmpeg
- **requests + fonttools** — on-demand Google Fonts fetching/caching

## License

MIT — use this freely as a starting point for your own quiz/video tooling.
