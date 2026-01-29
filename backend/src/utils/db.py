"""Database models, session, and repository."""

import logging
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from sqlalchemy import (DateTime, Index, Integer, String, Text, create_engine,
                        select)
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            sessionmaker)
from src.utils.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# --- Engine & Session ---

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database and create tables."""
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Models ---


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class Transcription(Base):
    """Transcription database model."""

    __tablename__ = "transcriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # PK
    audio_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )  # Audio file name, must be unique
    transcribed_text: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Full transcript text
    created_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # for readable string and formatting when logging
    def __repr__(self) -> str:
        return f"<Transcription(id={self.id}, filename='{self.audio_filename}')>"


# --- CRUD ops ---


class TranscriptionRepository:
    """Repository for transcription CRUD operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, audio_filename: str, transcribed_text: str) -> Transcription:
        """Create new transcription record."""
        transcription = Transcription(
            audio_filename=audio_filename,
            transcribed_text=transcribed_text,
        )
        self._db.add(transcription)
        self._db.commit()
        self._db.refresh(transcription)
        logger.info(f"Created transcription: {transcription.id}")
        return transcription

    def get_all(self) -> Sequence[Transcription]:
        """Get all transcriptions, ordered by most recent first."""
        stmt = select(Transcription).order_by(Transcription.created_timestamp.desc())
        return self._db.execute(stmt).scalars().all()
    
    # the file name all start with sample, so index won't help much
    # can think if users will search sample 1 full or just 1 --KIV
    def search_by_filename(self, filename_query: str) -> Sequence[Transcription]:
        """Search transcriptions by filename (partial match)."""
        stmt = (
            select(Transcription)
            .where(Transcription.audio_filename.contains(filename_query))
            .order_by(Transcription.created_timestamp.desc())
        )
        return self._db.execute(stmt).scalars().all()
