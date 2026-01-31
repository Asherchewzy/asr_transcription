"""Database models, session, and repository."""

import logging
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Sequence

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
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
    # file name, must be unique
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # PK
    audio_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    # nullable until transcription completes
    transcribed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    # processing, completed, failed
    status: Mapped[str] = mapped_column(
        String(50), default="processing", nullable=False
    )
    # celery task ID
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # error details if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # for readable string and formatting when logging
    def __repr__(self) -> str:
        """Return a readable representation for logs."""
        return (
            f"<Transcription(id={self.id}, filename='{self.audio_filename}', "
            f"status='{self.status}')>"
        )


# CRUD
class TranscriptionRepository:
    """Repository for transcription CRUD operations."""

    def __init__(self, db: Session) -> None:
        """Initialize repository with a database session."""
        self._db = db

    def create(
        self,
        audio_filename: str,
        transcribed_text: str | None = None,
        status: str = "processing",
        task_id: str | None = None,
    ) -> Transcription:
        """Create new transcription record."""
        transcription = Transcription(
            audio_filename=audio_filename,
            transcribed_text=transcribed_text,
            status=status,
            task_id=task_id,
        )
        self._db.add(transcription)
        self._db.commit()
        self._db.refresh(transcription)
        logger.info(f"Created transcription: {transcription.id} with status: {status}")
        return transcription

    def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[Transcription]:
        """Get all transcriptions, ordered by most recent first."""
        stmt = (
            select(Transcription)
            .order_by(Transcription.created_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return self._db.execute(stmt).scalars().all()

    def get_by_id(self, transcription_id: int) -> Transcription | None:
        """Get transcription by ID."""
        stmt = select(Transcription).where(Transcription.id == transcription_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> Sequence[Transcription]:
        """Get transcriptions by status."""
        stmt = (
            select(Transcription)
            .where(Transcription.status == status)
            .order_by(Transcription.created_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return self._db.execute(stmt).scalars().all()

    def get_by_task_id(self, task_id: str) -> Transcription | None:
        """Get transcription by Celery task ID."""
        stmt = select(Transcription).where(Transcription.task_id == task_id)
        return self._db.execute(stmt).scalar_one_or_none()

    # the file name all start with sample, so index won't help much
    def search_by_filename(self, filename_query: str) -> Sequence[Transcription]:
        """Search transcriptions by filename (partial match)."""
        stmt = (
            select(Transcription)
            .where(Transcription.audio_filename.contains(filename_query))
            .order_by(Transcription.created_timestamp.desc())
        )
        return self._db.execute(stmt).scalars().all()

    def update_transcription_text(self, transcription_id: int, text: str) -> None:
        """Update transcribed text."""
        transcription = self.get_by_id(transcription_id)
        if transcription:
            transcription.transcribed_text = text
            self._db.commit()
            logger.info(f"Updated transcription {transcription_id} with text")

    def update_transcription_status(self, transcription_id: int, status: str) -> None:
        """Update transcription status (processing, completed, failed)."""
        transcription = self.get_by_id(transcription_id)
        if transcription:
            transcription.status = status
            self._db.commit()
            logger.info(f"Updated transcription {transcription_id} status to: {status}")

    def update_transcription_error(self, transcription_id: int, error: str) -> None:
        """Update error message."""
        transcription = self.get_by_id(transcription_id)
        if transcription:
            transcription.error_message = error
            self._db.commit()
            logger.info(f"Updated transcription {transcription_id} with error")

    def update_task_id(self, transcription_id: int, task_id: str) -> None:
        """Update Celery task ID."""
        transcription = self.get_by_id(transcription_id)
        if transcription:
            transcription.task_id = task_id
            self._db.commit()
            logger.info(
                f"Updated transcription {transcription_id} with task_id: {task_id}"
            )
