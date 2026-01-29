"""Business logic service for transcription workflow."""

import logging

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.utils.db import Transcription, TranscriptionRepository
from src.services.file_service import FileService
from src.services.whisper_service import WhisperModelService

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service to orchestrate transcription workflow."""

    def __init__(
        self,
        db: Session,
        file_service: FileService,
        whisper_service: WhisperModelService,
    ) -> None:
        self._file_service = file_service
        self._whisper_service = whisper_service
        self._repository = TranscriptionRepository(db)

    async def process_transcription(self, file: UploadFile) -> Transcription:
        """Process complete transcription workflow.

        Steps:
        1. Validate file (extension, size, MIME type)
        2. Save file with unique name
        3. Transcribe audio using Whisper
        4. Save transcription to database
        """
        self._file_service.validate_file(file)
        filename, file_path = await self._file_service.save_file(file)

        try:
            transcribed_text = self._whisper_service.transcribe(file_path)
            transcription = self._repository.create(
                audio_filename=filename,
                transcribed_text=transcribed_text,
            )
            logger.info(f"Transcription completed: {transcription.id}")
            return transcription

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            self._file_service.delete_file(filename)
            raise
