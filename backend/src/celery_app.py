"""Celery application for async transcription tasks."""

import os
from celery import Celery
from src.utils.settings import get_settings
from src.services.whisper_service import WhisperModelService
from src.utils.db import get_db, TranscriptionRepository

settings = get_settings()

celery = Celery(
    'transcription_tasks',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3*60,  # 3 minutes max per task
    worker_prefetch_multiplier=1,  # how many it fetch from queue, so task dont get parked idle (task not in the superfast latency)
    result_expires=3600,  # 1 hour 
)


@celery.task(
    bind=True,
    name='transcription_tasks.transcribe_audio',
    autoretry_for=(Exception,),
    max_retries=3, 
    retry_backoff=True,
    retry_backoff_max=30,  
    retry_jitter=True #add randomness to avoid overwhlming
)
def transcribe_audio_task(self, file_path: str, transcription_id: int) -> dict:
    """
    Background task to transcribe audio file.

    Args:
        file_path: Absolute path to audio file on disk
        transcription_id: Database record ID

    Returns:
        dict: Task result with status and transcribed text
    """
    try:
        whisper_service = WhisperModelService()
        self.update_state(state='PROCESSING', meta={'status': 'Transcribing audio'})
        transcribed_text = whisper_service.transcribe(file_path)

        self.update_state(state='PROCESSING', meta={'status': 'Saving results'})

        db = next(get_db()) # next for generator, grab yielded sess
        try:
            repo = TranscriptionRepository(db)
            repo.update_transcription_text(transcription_id, transcribed_text)
            repo.update_transcription_status(transcription_id, 'completed')
        finally:
            db.close()

        return {
            'status': 'completed',
            'transcription_id': transcription_id,
            'text': transcribed_text
        }

    except Exception as e:
        db = next(get_db())
        try:
            repo = TranscriptionRepository(db)
            repo.update_transcription_status(transcription_id, 'failed')
            repo.update_transcription_error(transcription_id, str(e))
        finally:
            db.close()

        raise #go into retry
