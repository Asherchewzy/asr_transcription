# Audio Transcription App
Transcribe MP3 audio files using OpenAI Whisper Tiny.

## Contents
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Setup](#quick-setup)
- [Manual Setup](#manual-setup)
  - [Installations if you need](#installations-if-you-need)
  - [Sync packages](#sync-packages)
- [Starting the app](#starting-the-app)
  - [Editing configurations](#editing-configurations)
  - [Starting docker containers](#starting-docker-containers)
  - [Useful commands for clearing data](#useful-commands-for-clearing-data-for-clean-app-restart)
- [Access the app and API](#access-the-app-and-api-after-containers-are-up)
- [Run 3 unit tests](#run-3-unit-test-for-backend-and-frontend)

## Tech Stack
- Backend: FastAPI + Celery + Redis + SQLite
- Frontend: React + TypeScript + Vite
- ML Model: Whisper-tiny


## Project Structure
```text
.
├── backend/                    # FastAPI + Celery service
│   ├── src/
│   │   ├── services/          # Business logic (Celery, Whisper, file handling)
│   │   ├── utils/             # Database, schemas, settings, security
│   │   └── main.py            # FastAPI application entry point
│   ├── data/                  # SQLite database storage
│   ├── uploads/               # Uploaded audio files
│   ├── tests_special_3/       # Backend unit tests
│   ├── notebook/              # Development notebooks
│   ├── Dockerfile             # Docker image for backend
│   └── pyproject.toml         # Python dependencies (managed by uv)
│
├── frontend/                   # React + TypeScript app (Vite)
│   ├── src/
│   │   ├── components/        # React components (FileUpload, TranscriptionList, SearchBar)
│   │   ├── services/          # API client and validation
│   │   ├── types/             # TypeScript type definitions
│   │   ├── tests_special_3/   # Frontend unit tests
│   │   └── App.tsx            # Main application component
│   ├── Dockerfile             # Docker image for frontend
│   ├── package.json           # Node dependencies
│   └── vite.config.ts         # Vite configuration
│
├── sample_data/               # additional sample audio files for testing
├── docker-compose.yml         # Multi-container orchestration
├── setup.sh                   # Automated environment setup script
├── .env.example               # Environment configuration template
└── README.md
```


## Quick Setup

This set up will:
- Install `uv` if not present
- Check if you have `brew` installed
- Install `ffmpeg`, `Node.js`, `npm` via brew, if brew is installed
- Install `Python 3.11.14`
- Set up backend dependencies via `uv`
- Install frontend dependencies (npm packages)
- Check for FFmpeg and Node.js (required dependencies)

However, if this fails, please go through the "Installations if you need" and "Sync packages" section.
This setup does not install docker VM or daemons.

```bash
# by bash
bash setup.sh

# or run directly
chmod +x setup.sh
./setup.sh
```


## Manual Setup:
### Installations if you need:
**Docker:**
- Your choice of VM, this project uses colima:
    - `brew install colima`
    - `brew install docker docker-compose`

**UV for python:**
- check and download base on your os: `https://docs.astral.sh/uv/getting-started/installation/`

**Node and npm:**
- `brew install node`
- `npm install -D typescript ts-node @types/node`

**Additional dependencies:**
command line tool for audio/video
- `brew install ffmpeg`


### Sync packages
- **Backend:** `uv sync --extra dev` in backend/
- **Frontend:** `npm install` in frontend/

## Starting the app

### Editing configurations
- Edit configurations here: `.env.example`
- `export $(grep -v '^#' .env.example | xargs)` sets it as env variable while ignoring comments


### Starting docker containers
```bash
# start your vm if you have not
colima start

# from project root
export $(grep -v '^#' .env.example | xargs)
docker-compose up --build -d
```
- shut down docker containers `docker-compose down`
- force recreate `docker-compose up --build -d --force-recreate`

#### Useful commands for clearing data for clean app restart
```bash
# clear db data and uploads
rm -f backend/data/transcriptions.db
rm -rf backend/uploads/*

# clear model cache (optional; will re-download model)
rm -rf backend/model_cache
```

## Access the app and api after containers are up
- The app interface (Frontend): `http://localhost:3000`
- Swagger Backend API Docs: `http://localhost:8000/docs`

## Run 3 unit test for backend and frontend
**Backend**
```bash
# from project root
export $(grep -v '^#' .env.example | xargs)
cd backend
source .venv/bin/activate
python -m pytest -v
```

**Frontend**
```bash
# from project root
export $(grep -v '^#' .env.example | xargs)
cd frontend
npm run test
# press q to quit after
```
