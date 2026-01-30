"""Secure file handling service."""

import logging
import os
import re2 as re
from secrets import token_hex
from datetime import datetime, timezone
from pathlib import Path

import magic
from fastapi import HTTPException, UploadFile, status

from src.utils.settings import get_settings

logger = logging.getLogger(__name__)

# for mp3, audio/mpeg is official and audio/mp3 common non-standard
ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/mp3"}

# Maximum chunk size for reading files (64KB)
CHUNK_SIZE = 64 * 1024


class FileService:
    """Secure file handling service."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._upload_dir = Path(self._settings.upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file.

        Args:
            file: Uploaded file to validate

        Raises:
            HTTPException: If validation fails
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided",
            )

        # Check extension, size, type
        self._validate_extension(file.filename)
        self._validate_file_size(file)
        self._validate_mime_type(file)

    def _validate_extension(self, filename: str) -> None:
        """Validate file extension."""
        ext = Path(filename).suffix.lower()
        allowed = self._settings.allowed_extensions_list 

        if ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(allowed)}",
            )

    def _validate_file_size(self, file: UploadFile) -> None:
        """Validate file size using chunked reading."""
        max_size = self._settings.max_upload_size_bytes
        total_size = 0

        # Read in chunks to avoid memory exhaustion
        file.file.seek(0, os.SEEK_END)
        total_size = file.file.tell()
        file.file.seek(0)  # Reset file pointer

        if total_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {self._settings.max_upload_size_mb}MB",
            )

    # not comprehensive, future can consider parse and discard original/some kind of malware s
    def _validate_mime_type(self, file: UploadFile) -> None:
        """Validate MIME type using python-magic."""
        # Read first 2048 bytes to determine file type
        header = file.file.read(2048)
        file.file.seek(0)  # Reset file pointer to the start

        mime_type = magic.from_buffer(header, mime=True)

        if mime_type not in ALLOWED_MIME_TYPES:
            logger.warning(f"Invalid MIME type detected: {mime_type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid audio format. Only MP3 files are allowed.",
            )

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and injection attacks.

        Args:
            filename: Original filename from untrusted user input

        Returns:
            Sanitized filename safe for filesystem storage, always ending in .mp3
        """
        # filename without path components
        filename = os.path.basename(filename)

        # null bytes
        safe_name = filename.replace("\x00", "")

        # path traversal patterns
        safe_name = safe_name.replace("..", "").replace("/", "").replace("\\", "")

        # Keep only safe characters: alphanumeric, dash, underscore, period
        # Remove any HTML/script characters
        # here our 'sample 3.mp3' becomes 'sample_3.mp3' becos space not allowed
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", safe_name)  

        # collapse multiple underscores
        safe_name = re.sub(r"_+", "_", safe_name)

        # leading/trailing underscores and periods
        safe_name = safe_name.strip("_.")

        if not safe_name:
            safe_name = "unnamed"

        # partly yo make sure .mp3 extension, partly to not get something like .exe
        if not safe_name.lower().endswith(".mp3"):
            safe_name = safe_name + ".mp3"

        return safe_name

    def generate_unique_filename(self, original_filename: str) -> str:
        """Generate unique filename with timestamp and random suffix.

        Format: {name}_{timestamp}_{random}.mp3

        Args:
            original_filename: Original filename

        Returns:
            Unique filename
        """
        sanitized = self.sanitize_filename(original_filename)
        stem = Path(sanitized).stem # sample_3
        suffix = Path(sanitized).suffix # .mp3

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        random_suffix = token_hex(4)

        return f"{stem}_{timestamp}_{random_suffix}{suffix}"

    async def save_file(self, file: UploadFile) -> tuple[str, Path]:
        """Save uploaded file securely.

        Args:
            file: Uploaded file to save

        Returns:
            Tuple of (unique_filename, file_path)

        Raises:
            HTTPException: If save fails
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided",
            )

        # Generate unique filename
        unique_filename = self.generate_unique_filename(file.filename)
        file_path = self._upload_dir / unique_filename

        try:
            # save in small chunks to use low memory
            with open(file_path, "wb") as buffer:
                while chunk := await file.read(CHUNK_SIZE):
                    buffer.write(chunk)

            logger.info(f"File saved: {unique_filename}")
            return unique_filename, file_path

        except Exception as e:
            if file_path.exists():
                file_path.unlink() #delete partial file
            logger.error(f"Failed to save file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save file",
            )

    def delete_file(self, filename: str) -> bool:
        """Delete file from upload directory.

        Args:
            filename: Name of file to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self._upload_dir / self.sanitize_filename(filename)

        if file_path.exists():
            file_path.unlink()
            logger.info(f"File deleted: {filename}")
            return True

        return False


def get_file_service() -> FileService:
    """Get file service instance."""
    return FileService()

