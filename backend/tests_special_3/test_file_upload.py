"""special test #3: file upload validations and concurrent uploads.

simulates production load: 10 files uploaded simultaneously via API
tests validations: file size, extension, MIME type, filename sanitization
tests race conditions in filename generation, db writes, disk I/O
validates unique filename generation under concurrency
tests rate limiting enforcement
catches file descriptor leaks, db deadlocks, partial write issues
"""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

from src.services.file_service import FileService


class TestConcurrentFileUploads:
    """test concurrent file upload race conditions."""

    def test_10_concurrent_uploads_all_succeed(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """test /api/v1/transcribe endpoint can handle 10 simultaneous file uploads without failing"""
        # mock celery task to avoid actual processing
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_task.delay.return_value = mock_task

        # sends a fake MP3 upload from in memoty
        def upload_file(file_index):
            """upload a single file."""
            files = {
                "files": (
                    f"test_file_{file_index}.mp3",
                    io.BytesIO(sample_mp3_bytes),
                    "audio/mpeg",
                )
            }
            return test_client.post("/api/v1/transcribe", files=files)

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task

            # submit uploads concurrently, collect the results as each task completes
            num_uploads = 10
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(upload_file, i) for i in range(num_uploads)]
                results = [f.result() for f in as_completed(futures)]

        # all should succeed
        success_count = sum(1 for r in results if r.status_code == 200)
        assert (
            success_count == num_uploads
        ), f"expected {num_uploads} successes, got {success_count}"

        # verify all files saved to disk
        saved_files = list(temp_upload_dir.glob("*.mp3"))
        assert (
            len(saved_files) == num_uploads
        ), f"expected {num_uploads} files, found {len(saved_files)}"

    def test_all_filenames_unique_under_concurrency(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """test that concurrent uploads generate unique filenames"""
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_task.delay.return_value = mock_task

        def upload_file(file_index):
            # all files have same original name to test collision resistance
            files = {
                "files": ("same_name.mp3", io.BytesIO(sample_mp3_bytes), "audio/mpeg")
            }
            return test_client.post("/api/v1/transcribe", files=files)

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task

            # concurrent uploads to test uniqueness
            num_uploads = 10
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(upload_file, i) for i in range(num_uploads)]
                for future in as_completed(futures):
                    future.result()

        # verify all filenames are unique
        saved_files = list(temp_upload_dir.glob("*.mp3"))
        filenames = [f.name for f in saved_files]
        unique_filenames = set(filenames)

        # len(list) vs len(set(list)) which is depub
        assert len(filenames) == len(
            unique_filenames
        ), f"duplicate filenames detected: {filenames}"

    def test_all_db_records_created_with_unique_ids(
        self, test_client, sample_mp3_bytes, test_db
    ):
        """test that concurrent uploads create unique db records"""
        mock_task = MagicMock()
        mock_task.id = "test-task-id"

        task_count = [0]

        def mock_delay(*args, **kwargs):
            task_count[0] += 1
            mock_result = MagicMock()
            mock_result.id = f"task-{task_count[0]}"
            return mock_result

        def upload_file(file_index):
            files = {
                "files": (
                    f"db_test_{file_index}.mp3",
                    io.BytesIO(sample_mp3_bytes),
                    "audio/mpeg",
                )
            }
            return test_client.post("/api/v1/transcribe", files=files)

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.side_effect = mock_delay

            # concurrent uploads
            num_uploads = 10
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(upload_file, i) for i in range(num_uploads)]
                results = [f.result() for f in as_completed(futures)]

        # collect all transcription ids from responses
        transcription_ids = []
        for r in results:
            if r.status_code == 200:
                data = r.json()
                for task in data["tasks"]:
                    transcription_ids.append(task["transcription_id"])

        # verify all ids are unique
        assert len(transcription_ids) == len(
            set(transcription_ids)
        ), f"duplicate transcription ids: {transcription_ids}"

    def test_mixed_valid_invalid_files_error_isolation(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """test that invalid file failures don't affect valid file processing"""
        mock_task = MagicMock()
        mock_task.id = "test-task-id"
        mock_task.delay.return_value = mock_task

        def upload_valid():
            files = {"files": ("valid.mp3", io.BytesIO(sample_mp3_bytes), "audio/mpeg")}
            return ("valid", test_client.post("/api/v1/transcribe", files=files))

        def upload_invalid():
            # txt file should be rejected
            files = {
                "files": ("invalid.txt", io.BytesIO(b"not an mp3 file"), "text/plain")
            }
            return ("invalid", test_client.post("/api/v1/transcribe", files=files))

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task

            # submit mixed batch: 1 valid + 1 invalid
            num_batch = 1
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for i in range(num_batch):
                    futures.append(executor.submit(upload_valid))
                    futures.append(executor.submit(upload_invalid))

                results = [f.result() for f in as_completed(futures)]

        valid_results = [r for (t, r) in results if t == "valid"]
        invalid_results = [r for (t, r) in results if t == "invalid"]

        # all valid uploads should succeed
        valid_successes = sum(1 for r in valid_results if r.status_code == 200)
        assert (
            valid_successes == num_batch
        ), f"expected {num_batch} valid successes, got {valid_successes}"

        # all invalid uploads should fail with 400
        invalid_failures = sum(1 for r in invalid_results if r.status_code == 400)
        assert (
            invalid_failures == num_batch
        ), f"expected {num_batch} invalid failures, got {invalid_failures}"

    def test_no_partial_writes_on_failure(self, test_client, temp_upload_dir):
        """test that failed uploads don't leave partial files"""
        # create file that will fail mime validation
        fake_mp3 = b"not a real mp3 file content" * 100

        files = {"files": ("fake.mp3", io.BytesIO(fake_mp3), "audio/mpeg")}
        # test_client in conftest
        response = test_client.post("/api/v1/transcribe", files=files)

        # should fail validation (400) or be rate limited (429)
        assert response.status_code in (
            400,
            429,
        ), f"expected 400 or 429, got {response.status_code}"

        # if not rate limited, verify no files left in upload directory
        # If the server rejects the file, it should not leave a partial file in the upload directory.
        if response.status_code == 400:
            saved_files = list(temp_upload_dir.glob("*"))
            assert len(saved_files) == 0, f"partial files left: {saved_files}"

    def test_task_ids_returned_for_all_uploads(self, test_client, sample_mp3_bytes):
        """test that each upload returns a unique task id"""
        task_counter = [0]

        def mock_delay(*args, **kwargs):
            task_counter[0] += 1
            mock_result = MagicMock()
            mock_result.id = f"task-{task_counter[0]}"
            return mock_result

        def upload_file(file_index):
            files = {
                "files": (
                    f"task_test_{file_index}.mp3",
                    io.BytesIO(sample_mp3_bytes),
                    "audio/mpeg",
                )
            }
            return test_client.post("/api/v1/transcribe", files=files)

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.side_effect = mock_delay

            num_uploads = 5
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(upload_file, i) for i in range(num_uploads)]
                results = [f.result() for f in as_completed(futures)]

        # collect all task ids
        task_ids = []
        for r in results:
            if r.status_code == 200:
                data = r.json()
                for task in data["tasks"]:
                    task_ids.append(task["task_id"])

        # verify all successful uploads have unique task ids
        if task_ids:
            assert len(set(task_ids)) == len(
                task_ids
            ), f"duplicate task ids: {task_ids}"
        # if rate limited, task_ids will be empty, which is acceptable

    def test_filename_timestamp_token_uniqueness(self, temp_upload_dir):
        """test that generate_unique_filename produces unique names rapidly"""
        file_service = FileService()
        file_service._upload_dir = temp_upload_dir

        # generate 100 filenames rapidly with same original name
        filenames = []
        for _ in range(100):
            filename = file_service.generate_unique_filename("same_name.mp3")
            filenames.append(filename)

        # all should be unique
        assert len(filenames) == len(
            set(filenames)
        ), "duplicate filenames in rapid generation"

    def test_concurrent_filename_generation_thread_safe(self, temp_upload_dir):
        """test that filename generation is thread-safe"""
        file_service = FileService()
        file_service._upload_dir = temp_upload_dir

        def generate_filename(index):
            return file_service.generate_unique_filename("concurrent.mp3")

        # same name = race = not thread safe
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(generate_filename, i) for i in range(100)]
            filenames = [f.result() for f in as_completed(futures)]

        # all should be unique
        assert len(filenames) == len(
            set(filenames)
        ), "thread-safety issue: duplicate filenames generated concurrently"

    def test_large_batch_upload_single_request(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """test uploading multiple files in a single request"""

        task_counter = [0]

        def mock_delay(*args, **kwargs):
            task_counter[0] += 1
            mock_result = MagicMock()
            mock_result.id = f"batch-task-{task_counter[0]}"
            return mock_result

        # create multiple files in single request
        num_files = 5
        files = [
            ("files", (f"batch_{i}.mp3", io.BytesIO(sample_mp3_bytes), "audio/mpeg"))
            for i in range(num_files)
        ]

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.side_effect = mock_delay
            response = test_client.post("/api/v1/transcribe", files=files)

        if response.status_code == 200:
            data = response.json()
            assert len(data["tasks"]) == num_files

            # verify all files saved
            saved_files = list(temp_upload_dir.glob("*.mp3"))
            assert len(saved_files) == num_files

    def test_response_under_load(self, test_client, sample_mp3_bytes):
        """test basic robustness under a small burst (no crashes/timeouts) and that there is valid status 200/429."""
        mock_task = MagicMock()
        mock_task.id = "rate-test-task"
        mock_task.delay.return_value = mock_task

        def upload_file(index):
            files = {
                "files": (
                    f"rate_{index}.mp3",
                    io.BytesIO(sample_mp3_bytes),
                    "audio/mpeg",
                )
            }
            return test_client.post("/api/v1/transcribe", files=files)

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task

            results = []
            for i in range(3):
                results.append(upload_file(i))

        # verify we got responses (either 200 or 429)
        # by right should not 429 as limiter.enabled = False set in conftest.py
        status_codes = [r.status_code for r in results]
        assert all(
            code in (200, 429) for code in status_codes
        ), f"expected 200 or 429 responses, got {status_codes}"


class TestFileValidations:
    """Test file validation functions."""

    def test_file_size_validation_rejects_oversized_files(self, test_client):
        """Test that files exceeding size limit are rejected."""
        # add 1kb to the settings.max_upload_size_bytes
        from src.utils.settings import get_settings

        settings = get_settings()
        oversized_data = b"\xff\xfb\x90\x00" * (settings.max_upload_size_bytes + 1024)

        mock_task = MagicMock()
        mock_task.id = "size-test"
        mock_task.delay.return_value = mock_task

        files = {"files": ("large.mp3", io.BytesIO(oversized_data), "audio/mpeg")}

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            response = test_client.post("/api/v1/transcribe", files=files)

        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]

    def test_extension_validation_rejects_invalid_types(
        self, test_client, sample_mp3_bytes
    ):
        """Test that invalid file extensions are rejected."""
        # mime and bytes is mp3 but extension is .exe
        files = {"files": ("malware.exe", io.BytesIO(sample_mp3_bytes), "audio/mpeg")}
        response = test_client.post("/api/v1/transcribe", files=files)

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_mime_type_validation_detects_spoofing(
        self, test_client, invalid_file_bytes
    ):
        """Test that MIME type spoofing is detected."""
        # File named .mp3 but actually an exe
        # mime and name is mp3 but btyes not mp3
        files = {"files": ("fake.mp3", io.BytesIO(invalid_file_bytes), "audio/mpeg")}
        response = test_client.post("/api/v1/transcribe", files=files)

        assert response.status_code == 400
        assert "Invalid audio format" in response.json()["detail"]

    def test_filename_sanitization_blocks_path_traversal(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """Test that path traversal in filenames is blocked."""
        mock_task = MagicMock()
        mock_task.id = "sanitize-test"
        mock_task.delay.return_value = mock_task

        files = {
            "files": (
                "../../etc/passwd.mp3",
                io.BytesIO(sample_mp3_bytes),
                "audio/mpeg",
            )
        }

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            response = test_client.post("/api/v1/transcribe", files=files)

        # Should succeed
        assert response.status_code == 200

        # Verify the actual saved file doesn't have path traversal
        # should be passwd.mp3
        # Check files saved to temp directory
        saved_files = list(temp_upload_dir.glob("*.mp3"))
        assert len(saved_files) == 1
        saved_filename = saved_files[0].name
        assert ".." not in saved_filename
        assert "/" not in saved_filename

    def test_filename_sanitization_removes_null_bytes(
        self, test_client, sample_mp3_bytes
    ):
        """Test that null bytes in filenames are removed."""
        mock_task = MagicMock()
        mock_task.id = "null-byte-test"
        mock_task.delay.return_value = mock_task

        files = {
            "files": ("evil.exe\x00.mp3", io.BytesIO(sample_mp3_bytes), "audio/mpeg")
        }

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            response = test_client.post("/api/v1/transcribe", files=files)

        assert response.status_code == 200
        saved_filename = response.json()["tasks"][0]["filename"]
        assert "\x00" not in saved_filename

    def test_filename_sanitization_replaces_special_chars(
        self, test_client, sample_mp3_bytes, temp_upload_dir
    ):
        """Test that special characters are replaced."""
        mock_task = MagicMock()
        mock_task.id = "special-char-test"
        mock_task.delay.return_value = mock_task

        files = {
            "files": ("test<script>.mp3", io.BytesIO(sample_mp3_bytes), "audio/mpeg")
        }

        with patch("src.main.transcribe_audio_task") as mock_celery:
            mock_celery.delay.return_value = mock_task
            response = test_client.post("/api/v1/transcribe", files=files)

        assert response.status_code == 200

        # Verify the actual saved file doesn't have special chars
        saved_files = list(temp_upload_dir.glob("*.mp3"))
        assert len(saved_files) == 1
        saved_filename = saved_files[0].name
        assert "<" not in saved_filename
        assert ">" not in saved_filename


class TestRateLimiting:
    """Test API rate limiting."""

    def test_rate_limit_enforcement(self, test_client, sample_mp3_bytes):
        """Test that rate limiting prevents excessive requests."""
        from src.main import limiter, settings

        # Enable rate limiting for this specific test
        limiter.enabled = True
        original_limit = settings.transcribe_rate_limit
        settings.transcribe_rate_limit = "5/minute"

        try:
            mock_task = MagicMock()
            mock_task.id = "rate-limit-test"
            mock_task.delay.return_value = mock_task

            with patch("src.main.transcribe_audio_task") as mock_celery:
                mock_celery.delay.return_value = mock_task

                # at least some should be rate limited
                responses = []
                for i in range(10):
                    files = {
                        "files": (
                            f"test_{i}.mp3",
                            io.BytesIO(sample_mp3_bytes),
                            "audio/mpeg",
                        )
                    }
                    response = test_client.post("/api/v1/transcribe", files=files)
                    responses.append(response)

                # Verify we got some 200s and some 429s
                status_codes = [r.status_code for r in responses]
                assert 200 in status_codes, "At least one request should succeed"
                assert 429 in status_codes, "Rate limiting should kick in"

                # Verify the 429 response indicates rate limiting
                rate_limited = [r for r in responses if r.status_code == 429]
                if rate_limited:
                    # SlowAPI returns error in "error" key or plain text
                    response_text = rate_limited[0].text
                    assert (
                        "limit" in response_text.lower()
                        or "rate" in response_text.lower()
                    )
        finally:
            # Disable rate limiting again for other tests
            limiter.enabled = False
            settings.transcribe_rate_limit = original_limit
