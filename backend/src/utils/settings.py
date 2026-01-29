import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        # Application
        self.app_name = os.getenv("APP_NAME", "Audio Transcription API")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"

        # db
        self.database_url = os.getenv(
            "DATABASE_URL", "sqlite:///./data/transcriptions.db"
        )

        # Storage
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "./uploads"))
        self.model_cache_dir = Path(os.getenv("MODEL_CACHE_DIR", "./model_cache"))

        # avg kbps = 125kbps
        # minutes = (max_size_mb * 8_000_000) / (avg_kbps * 1000 * 60) 
        # 15mb = 16min audio
        self.max_upload_size_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
        self.allowed_audio_extensions = os.getenv("ALLOWED_AUDIO_EXTENSIONS", ".mp3")

        # Whisper Model
        self.whisper_model_name = os.getenv("WHISPER_MODEL_NAME", "openai/whisper-tiny")
        self.whisper_chunk_length_s = int(os.getenv("WHISPER_CHUNK_LENGTH_S", "30"))
        self.whisper_stride_length_s = (4, 4)

        # CORS
        self.cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")

        # Rate Limiting
        self.transcribe_rate_limit = os.getenv("TRANSCRIBE_RATE_LIMIT", "10/minute")

    @property
    def max_upload_size_bytes(self):
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_extensions_list(self):
        return [ext.strip() for ext in self.allowed_audio_extensions.split(",")]

    @property
    def cors_origins_list(self):
        return [origin.strip() for origin in self.cors_origins.split(",")]


# module-level cache + singleton, first caller from any importer init it and later call reuse
_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
