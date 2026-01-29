"""Main FastAPI application with API routes."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (Depends, FastAPI, File, HTTPException, Query, Request,
                     UploadFile, status)
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from src.utils.security import sanitize_search_query
from src.utils.db import TranscriptionRepository, get_db, init_db
from src.utils.schemas import (HealthResponse, TranscriptionResponse,
                               TranscriptionSearchResponse)
from src.services.file_service import FileService, get_file_service
from src.services.transcription_service import TranscriptionService
from src.services.whisper_service import (WhisperModelService,
                                          get_whisper_service)
from src.utils.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# https://slowapi.readthedocs.io/en/latest/
limiter = Limiter(key_func=get_remote_address)  # ip


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # load up early so first request is faster
    logger.info("Starting application...")
    init_db()
    logger.info("Database initialized")

    whisper = get_whisper_service()
    logger.info(f"Whisper model loaded on device: {whisper.device}")

    yield  # above startup then pause FastAPI serves requests

    logger.info("Shutting down application...")


# /docs to see swagger
app = FastAPI(
    title=settings.app_name,
    description="Audio transcription API using Whisper Tiny model",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- Routes ---


@app.get("/")
async def root():
    """Root endpoint redirect to docs."""
    return {"message": "Ok"}

@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    whisper: WhisperModelService = Depends(get_whisper_service),
) -> HealthResponse:
    """Check API health status and model availability."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        model_loaded=whisper.is_loaded,
        device=whisper.device,
    )


@app.post(
    "/api/v1/transcribe",
    response_model=TranscriptionResponse,
    tags=["Transcription"],
    responses={
        400: {"description": "Invalid file type or format"},
        413: {"description": "File too large"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Transcription failed"},
    },
)
@limiter.limit(lambda: settings.transcribe_rate_limit)
async def transcribe_audio(
    request: Request,  # required for slowapi rate limiting
    file: UploadFile = File(
        ..., description="MP3 audio file to transcribe"
    ),  # ... = required
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service),
    whisper_service: WhisperModelService = Depends(get_whisper_service),
) -> TranscriptionResponse:
    """Upload and transcribe audio file. Rate limited per IP."""
    service = TranscriptionService(
        db=db,
        file_service=file_service,
        whisper_service=whisper_service,
    )
    transcription = await service.process_transcription(file)

    return TranscriptionResponse(
        id=transcription.id,
        audio_filename=transcription.audio_filename,
        transcribed_text=transcription.transcribed_text,
        created_timestamp=transcription.created_timestamp,
    )


@app.get(
    "/api/v1/transcriptions",
    response_model=list[TranscriptionResponse],
    tags=["Transcriptions"],
)
async def list_transcriptions(
    db: Session = Depends(get_db),
) -> list[TranscriptionResponse]:
    """Get all transcriptions, ordered by most recent first."""
    repository = TranscriptionRepository(db)
    transcriptions = repository.get_all()

    return [
        TranscriptionResponse(
            id=t.id,
            audio_filename=t.audio_filename,
            transcribed_text=t.transcribed_text,
            created_timestamp=t.created_timestamp,
        )
        for t in transcriptions
    ]


@app.get(
    "/api/v1/search",
    response_model=TranscriptionSearchResponse,
    tags=["Search"],
)
async def search_transcriptions(
    filename: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> TranscriptionSearchResponse:
    """Search transcriptions by filename (partial match)."""
    sanitized_query = sanitize_search_query(filename)

    if not sanitized_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid search query",
        )

    repository = TranscriptionRepository(db)
    results = repository.search_by_filename(sanitized_query)

    return TranscriptionSearchResponse(
        results=[
            TranscriptionResponse(
                id=t.id,
                audio_filename=t.audio_filename,
                transcribed_text=t.transcribed_text,
                created_timestamp=t.created_timestamp,
            )
            for t in results
        ],
        query=sanitized_query,
    )
