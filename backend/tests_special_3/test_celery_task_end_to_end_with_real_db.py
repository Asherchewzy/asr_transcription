"""special test #1: celery task end-to-end with real database.

tests the most critical async workflow: transcribe_audio_task
uses real database (not mocked) to catch transaction/commit issues
exercises full lifecycle: pending → processing → completed
catches issues unit tests miss: db session lifecycle in background tasks
"""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.db import TranscriptionRepository


class TestCeleryTaskEndToEnd:
    """end-to-end tests for transcribe_audio_task with real database."""

    def test_transcribe_success_updates_db_status_to_completed(self, test_db):
        """test happy path: task completes and updates db status to completed"""
        # arrange - create initial db record
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="test_audio.mp3", transcribed_text=None, status="processing"
        )
        transcription_id = transcription.id

        # mock whisper service to return known text
        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = "hello world transcription"

        # mock get_db to return our test session
        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                # mock update_state to avoid task_id requirement when running directly
                with patch.object(transcribe_audio_task, "update_state"):
                    result = transcribe_audio_task.run(
                        file_path="/fake/path/test.mp3",
                        transcription_id=transcription_id,
                    )

        # assert - verify db was updated
        updated = repo.get_by_id(transcription_id)
        assert updated.status == "completed"
        assert updated.transcribed_text == "hello world transcription"
        assert result["status"] == "completed"
        assert result["text"] == "hello world transcription"

    def test_transcribe_updates_state_to_processing(self, test_db):
        """test that task updates state during processing"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="test_audio_2.mp3",
            transcribed_text=None,
            status="processing",
        )
        transcription_id = transcription.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = "transcribed text"

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                # mock update_state to avoid task_id requirement
                with patch.object(transcribe_audio_task, "update_state") as mock_update:
                    result = transcribe_audio_task.run(
                        file_path="/fake/path.mp3", transcription_id=transcription_id
                    )
                    # verify update_state was called with PROCESSING state
                    assert mock_update.called
                    mock_update.assert_any_call(
                        state="PROCESSING", meta={"status": "Transcribing audio"}
                    )

        # verify task completed successfully
        assert result["status"] == "completed"

    def test_transcribe_failure_updates_db_to_failed(self, test_db):
        """test that whisper failure updates db status to failed"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="test_fail.mp3", transcribed_text=None, status="processing"
        )
        transcription_id = transcription.id

        # mock whisper to raise exception
        mock_whisper = MagicMock()
        mock_whisper.transcribe.side_effect = Exception("whisper model error")

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    with pytest.raises(Exception, match="whisper model error"):
                        transcribe_audio_task.run(
                            file_path="/fake/path.mp3",
                            transcription_id=transcription_id,
                        )

        # verify db was updated to failed with error message
        updated = repo.get_by_id(transcription_id)
        assert updated.status == "failed"
        assert "whisper model error" in updated.error_message

    def test_transcribe_file_not_found_sets_error(self, test_db):
        """test that file not found error is captured in db"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="missing.mp3", transcribed_text=None, status="processing"
        )
        transcription_id = transcription.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.side_effect = FileNotFoundError("audio file not found")

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    with pytest.raises(FileNotFoundError):
                        transcribe_audio_task.run(
                            file_path="/nonexistent/path.mp3",
                            transcription_id=transcription_id,
                        )

        updated = repo.get_by_id(transcription_id)
        assert updated.status == "failed"
        assert "not found" in updated.error_message.lower()

    def test_transcribe_returns_correct_result_dict(self, test_db):
        """test that task returns correctly formatted result dictionary"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="result_test.mp3", transcribed_text=None, status="processing"
        )
        transcription_id = transcription.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = "the transcribed text"

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    result = transcribe_audio_task.run(
                        file_path="/fake/path.mp3", transcription_id=transcription_id
                    )

        # verify result structure
        assert isinstance(result, dict)
        assert "status" in result
        assert "transcription_id" in result
        assert "text" in result
        assert result["status"] == "completed"
        assert result["transcription_id"] == transcription_id
        assert result["text"] == "the transcribed text"

    def test_transcribe_empty_text_still_completes(self, test_db):
        """test that empty transcription (silence) still marks as completed"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="silence.mp3", transcribed_text=None, status="processing"
        )
        transcription_id = transcription.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = ""  # empty transcription

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    result = transcribe_audio_task.run(
                        file_path="/fake/path.mp3", transcription_id=transcription_id
                    )

        updated = repo.get_by_id(transcription_id)
        assert updated.status == "completed"
        assert updated.transcribed_text == ""
        assert result["status"] == "completed"

    def test_db_updates_both_text_and_status(self, test_db):
        """test that both text and status are updated in sequence"""
        repo = TranscriptionRepository(test_db)
        transcription = repo.create(
            audio_filename="both_updates.mp3",
            transcribed_text=None,
            status="processing",
        )
        transcription_id = transcription.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = "transcribed content"

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    transcribe_audio_task.run(
                        file_path="/fake/path.mp3", transcription_id=transcription_id
                    )

        updated = repo.get_by_id(transcription_id)
        # both should be updated
        assert updated.transcribed_text == "transcribed content"
        assert updated.status == "completed"

    def test_multiple_sequential_tasks_isolated(self, test_db):
        """test that multiple tasks don't interfere with each other"""
        repo = TranscriptionRepository(test_db)

        # create two transcriptions
        t1 = repo.create(audio_filename="task1.mp3", status="processing")
        t1_id = t1.id  # save id before session operations
        t2 = repo.create(audio_filename="task2.mp3", status="processing")
        t2_id = t2.id  # save id before session operations

        mock_whisper = MagicMock()
        mock_whisper.transcribe.side_effect = ["text for task 1", "text for task 2"]

        def mock_get_db():
            yield test_db

        with patch(
            "src.services.celery_app.WhisperModelService", return_value=mock_whisper
        ):
            with patch("src.services.celery_app.get_db", mock_get_db):
                from src.services.celery_app import transcribe_audio_task

                with patch.object(transcribe_audio_task, "update_state"):
                    transcribe_audio_task.run(
                        file_path="/path/task1.mp3", transcription_id=t1_id
                    )
                    transcribe_audio_task.run(
                        file_path="/path/task2.mp3", transcription_id=t2_id
                    )

        # verify each task updated its own record
        updated1 = repo.get_by_id(t1_id)
        updated2 = repo.get_by_id(t2_id)

        assert updated1.transcribed_text == "text for task 1"
        assert updated2.transcribed_text == "text for task 2"
        assert updated1.status == "completed"
        assert updated2.status == "completed"
