"""Main FastAPI application with API routes."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from celery.result import AsyncResult
from fastapi import (Depends, FastAPI, File, HTTPException, Query, Request,
                     UploadFile, status)
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.services.celery_app import celery, transcribe_audio_task
from src.services.file_service import FileService, get_file_service
from src.services.whisper_service import (WhisperModelService,
                                          get_whisper_service)
from src.utils.db import TranscriptionRepository, get_db, init_db
from src.utils.schemas import (HealthResponse, TaskStatusResponse,
                               TranscriptionBatchResponse,
                               TranscriptionResponse,
                               TranscriptionSearchResponse,
                               TranscriptionTaskResponse)
from src.utils.security import sanitize_search_query
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


@app.get("/")
async def root():
    """Root endpoint redirect to docs."""
    return {"message": "Ok"}


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health_check(
    whisper: WhisperModelService = Depends(get_whisper_service),
    db: Session = Depends(get_db),
) -> HealthResponse:
    """Check API health status including all dependencies."""
    # Check Whisper model
    model_healthy = whisper.is_loaded

    # Check database
    db_healthy = False
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    # Check Redis/Celery broker
    redis_healthy = False
    try:
        celery.broker_connection().ensure_connection(max_retries=1)
        redis_healthy = True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    # Check Celery workers
    celery_workers_healthy = False
    try:
        stats = celery.control.inspect().stats()
        celery_workers_healthy = stats is not None and len(stats) > 0
    except Exception as e:
        logger.error(f"Celery worker health check failed: {e}")

    # Overall status
    all_healthy = all(
        [model_healthy, db_healthy, redis_healthy, celery_workers_healthy]
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(),
        model_loaded=model_healthy,
        device_info=whisper.device,
        db_healthy=db_healthy,
        redis_healthy=redis_healthy,
        celery_workers_active=celery_workers_healthy,
    )


@app.post(
    "/api/v1/transcribe",
    response_model=TranscriptionBatchResponse,
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
    files: list[UploadFile] = File(
        ..., description="MP3 audio files to transcribe"
    ),  # ... = required
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service),
) -> TranscriptionBatchResponse:
    """Upload and transcribe audio files asynchronously. Returns task IDs for status polling."""
    repo = TranscriptionRepository(db)
    results = []

    for file in files:
        file_service.validate_file(file)
        unique_filename, file_path = await file_service.save_file(file)

        # Create database record with status="processing"
        transcription = repo.create(
            audio_filename=unique_filename, transcribed_text=None, status="processing"
        )

        # celery
        task = transcribe_audio_task.delay(str(file_path), transcription.id)

        repo.update_task_id(transcription.id, task.id)

        results.append(
            TranscriptionTaskResponse(
                task_id=task.id,
                transcription_id=transcription.id,
                filename=file.filename or unique_filename,
                status="processing",
            )
        )

    return TranscriptionBatchResponse(tasks=results)


@app.get(
    "/api/v1/status/{task_id}",
    response_model=TaskStatusResponse,
    tags=["Transcription"],
)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
) -> TaskStatusResponse:
    """Check status of a transcription task."""
    task = AsyncResult(task_id, app=celery)
    repo = TranscriptionRepository(db)

    if task.state == "PENDING":
        return TaskStatusResponse(status="pending", task_id=task_id)
    elif task.state == "PROCESSING":
        return TaskStatusResponse(
            status="processing",
            task_id=task_id,
            meta=task.info,  # transcribing or saving
        )
    elif task.state == "SUCCESS":
        transcription = repo.get_by_task_id(task_id)
        if transcription:
            return TaskStatusResponse(
                status="completed",
                task_id=task_id,
                transcription_id=transcription.id,
                text=transcription.transcribed_text,
            )
        return TaskStatusResponse(status="completed", task_id=task_id)
    elif task.state == "FAILURE":
        transcription = repo.get_by_task_id(task_id)
        error_msg = transcription.error_message if transcription else str(task.info)
        return TaskStatusResponse(status="failed", task_id=task_id, error=error_msg)
    else:
        return TaskStatusResponse(status=task.state.lower(), task_id=task_id)


@app.get(
    "/api/v1/transcriptions",
    response_model=list[TranscriptionResponse],
    tags=["Transcriptions"],
)
async def list_transcriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = Query(
        None, description="Filter by status: completed, processing, failed"
    ),
    db: Session = Depends(get_db),
) -> list[TranscriptionResponse]:
    """Get all transcriptions, ordered by most recent first. Optional status filter."""
    repository = TranscriptionRepository(db)

    if status:
        transcriptions = repository.get_by_status(status, skip, limit)
    else:
        transcriptions = repository.get_all(skip, limit)

    return [
        TranscriptionResponse(
            id=t.id,
            audio_filename=t.audio_filename,
            transcribed_text=t.transcribed_text,
            created_timestamp=t.created_timestamp,
            status=t.status,
            task_id=t.task_id,
            error_message=t.error_message,
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
                status=t.status,
                task_id=t.task_id,
                error_message=t.error_message,
            )
            for t in results
        ],
        query=sanitized_query,
    )
