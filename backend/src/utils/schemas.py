"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    model_loaded: bool
    device_info: str


class TranscriptionResponse(BaseModel):
    """Transcription API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    audio_filename: str
    transcribed_text: str | None = None
    created_timestamp: datetime
    status: str = 'processing'
    task_id: str | None = None
    error_message: str | None = None


class TranscriptionTaskResponse(BaseModel):
    """Response for async transcription task."""

    task_id: str
    transcription_id: int
    filename: str
    status: str


class TranscriptionBatchResponse(BaseModel):
    """Batch transcription response."""

    tasks: list[TranscriptionTaskResponse]


class TaskStatusResponse(BaseModel):
    """Task status response."""

    status: str
    task_id: str
    transcription_id: int | None = None
    text: str | None = None
    error: str | None = None
    meta: dict | None = None


class TranscriptionSearchResponse(BaseModel):
    """Transcription search results."""

    results: list[TranscriptionResponse]
    query: str
