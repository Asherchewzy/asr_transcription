# Audio Transcription App
Transcribe MP3 audio files using OpenAI Whisper Tiny.

## Contents
- [Tech Stack](#tech-stack)
- [Project structure](#project-structure)
- [Installations](#installations)
- [Sync packages](#sync-packages)
- [Editing configurations](#editing-configurations)
- [Starting app with docker](#starting-app-with-docker)
- [Useful commands for clearing data for clean app restart](#useful-commands-for-clearing-data-for-clean-app-restart)
- [Access the app and api after containers are up](#access-the-app-and-api-after-containers-are-up)
- [Run 3 unit test for backend and frontend](#run-3-unit-test-for-backend-and-frontend)

## Tech Stack
- Backend: FastAPI + Celery + Redis + SQLite
- Frontend: React + TypeScript + Vite
- ML Model: Whisper-tiny


## Project structure:
```text
.
├── backend/            # FastAPI + Celery service
│   ├── src/
│   ├── data/
│   ├── uploads/
│   └── tests_special_3/
├── frontend/           # React app (Vite)
│   └── src/
├── sample_data/        # Sample audio files
├── docker-compose.yml
└── README.md
```


### Installations:
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


## Sync packages
- **Backend:** `uv sync` in backend/
- **Frontend:** `npm install` in frontend/


## Editing configurations 
- Edit configurations here: `.env.example`
- `export $(grep -v '^#' .env.example | xargs)` sets it as env variable while ignoring comments


## Starting app with docker
```bash
# start your vm if you have not
colima start

# from project root
export $(grep -v '^#' .env.example | xargs)
docker-compose up --build -d
```
- shut down docker containers `docker-compose down`
- force recreate `docker-compose up --build -d --force-recreate`

### Useful commands for clearing data for clean app restart
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
                                                                            
