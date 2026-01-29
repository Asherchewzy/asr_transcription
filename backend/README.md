Backend quickstart

## Backend local setup
- Install uv (follow instruction base on your os): `https://docs.astral.sh/uv/getting-started/installation/`
- Navigate into backend: `cd backend/`
- Install dependencies: `uv sync` or `uv sync --extra dev` if you like to add optional dependencies.
- Activate venv: `source .venv/bin/activate`

## Testing endpoints
- Load env variables: `export $(grep -v '^#' .env.example | xargs)` --> easier than source command if your file has a lot of hashtags 
- Start API (venv active): `python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`.
- Open docs at http://127.0.0.1:8000/docs for swagger (recommend this to curl for ui friendly version).
- Sample calls using curl (run from `backend/`):
  - Health: `curl http://127.0.0.1:8000/api/v1/health`
  - Transcribe file "../Sample 1.mp3": `curl -F "file=@../Sample 1.mp3;type=audio/mpeg" http://127.0.0.1:8000/api/v1/transcribe`
  - List: `curl http://127.0.0.1:8000/api/v1/transcriptions`
  - Search: `curl "http://127.0.0.1:8000/api/v1/search?filename=Sample_1"`  
    - currently we save files with underscore, so search need to find Sample_1 instead of Sample 1 (not case-sensitive).