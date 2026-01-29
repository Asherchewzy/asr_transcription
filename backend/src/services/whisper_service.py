"""Thread-safe singleton service for Whisper model."""

import logging
import os
import threading
from pathlib import Path
from typing import Any

import torch
from transformers import pipeline

from src.utils.settings import get_settings

logger = logging.getLogger(__name__)


class WhisperModelService:
    """Thread-safe singleton pattern for Whisper model caching.

    Loading once per application lifecycle saves memory and improves response time for subsequent requests.
    """

    _instance: "WhisperModelService | None" = None 
    _lock: threading.Lock = threading.Lock() 
    _initialized: bool = False 

    def __new__(cls) -> "WhisperModelService":
        """Create singleton instance with double-checked locking."""
        if cls._instance is None:
            with cls._lock: 
                if cls._instance is None: 
                    cls._instance = super().__new__(cls) 
        return cls._instance

    def __init__(self) -> None:
        """Initialize model on first instantiation."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self._settings = get_settings()
            self._device = self._setup_device()
            self._pipeline = self._load_model()
            self._initialized = True

            logger.info(f"WhisperModelService initialized on device: {self._device}")

    def _setup_device(self) -> str:
        """Select best available device: CUDA -> MPS -> CPU."""
        if torch.cuda.is_available():
            device = "cuda"
            logger.info("Using CUDA device")
        elif torch.backends.mps.is_available():
            # Enable MPS fallback 
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
            device = "mps"
            logger.info("Using MPS device (Apple Silicon)")
        else:
            device = "cpu"
            logger.info("Using CPU device")
        return device

    def _load_model(self) -> Any:
        """Load Whisper pipeline with caching."""
        cache_dir = Path(self._settings.model_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Loading model: {self._settings.whisper_model_name}")
        logger.info(f"Cache directory: {cache_dir}")

        pipe = pipeline(
            "automatic-speech-recognition",
            model=self._settings.whisper_model_name,
            device=self._device,
            model_kwargs={"cache_dir": str(cache_dir)},
        )

        logger.info("Model loaded successfully")
        return pipe

    @property
    def device(self) -> str:
        """Get the device the model is running on."""
        return self._device

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._initialized and self._pipeline is not None

    def transcribe(
        self,
        audio_path: str | Path,
    ) -> str:
        """Transcribe audio file and return text.

        Args:
            audio_path: Path to the audio file

        Returns:
            Transcribed text string
        """
        if not self.is_loaded:
            raise RuntimeError("Whisper model not loaded")

        logger.info(f"Transcribing: {audio_path}")

        result = self._pipeline(
            str(audio_path),
            chunk_length_s=self._settings.whisper_chunk_length_s,
            stride_length_s=self._settings.whisper_stride_length_s,
        )

        text = result.get("text", "").strip()
        logger.info(f"Transcription complete: {len(text)} characters")

        return text


def get_whisper_service() -> WhisperModelService:
    """Get Whisper model service singleton instance."""
    return WhisperModelService()
