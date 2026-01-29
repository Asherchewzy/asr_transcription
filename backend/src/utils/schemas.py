"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    model_loaded: bool
    device: str


class TranscriptionResponse(BaseModel):
    """Transcription API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    audio_filename: str
    transcribed_text: str
    created_timestamp: datetime


class TranscriptionSearchResponse(BaseModel):
    """Transcription search results."""

    results: list[TranscriptionResponse]
    query: str
