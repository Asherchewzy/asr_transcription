"""Shared pytest fixtures for tests_special_3."""

import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.services.file_service import FileService, get_file_service
from src.utils.db import Base, get_db

# Test database - use StaticPool for in-memory sqlite thread safety
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test function."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def temp_upload_dir():
    """Create temporary upload directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_client(test_db, temp_upload_dir):
    """Create test client with mocked dependencies."""

    from src.main import app, limiter

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Mock file service to use temp directory
    mock_file_service = FileService()
    mock_file_service._upload_dir = temp_upload_dir

    def override_get_file_service():
        return mock_file_service

    app.dependency_overrides[get_file_service] = override_get_file_service

    # Disable rate limiting for tests by setting enabled=False on the actual limiter
    original_enabled = limiter.enabled
    limiter.enabled = False

    with TestClient(app) as client:
        yield client

    # Restore original state
    limiter.enabled = original_enabled
    app.dependency_overrides.clear()


@pytest.fixture
def sample_mp3_bytes():
    """Create valid MP3 file bytes."""
    mp3_header = b"ID3\x04\x00\x00\x00\x00\x00\x00"
    mp3_data = b"\xff\xfb\x90\x00" * 100
    return mp3_header + mp3_data


@pytest.fixture
def large_mp3_bytes():
    """Create oversized MP3 file bytes (exceeds 15MB limit)."""
    mp3_header = b"ID3\x04\x00\x00\x00\x00\x00\x00"
    # Create ~20MB file
    mp3_data = b"\xff\xfb\x90\x00" * (5 * 1024 * 1024)
    return mp3_header + mp3_data


@pytest.fixture
def invalid_file_bytes():
    """Create non-MP3 file bytes (exe file)."""
    return b"MZ" + b"\x00" * 2046  # PE/exe header
