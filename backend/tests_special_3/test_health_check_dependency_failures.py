"""special test #2: health check dependency failures.

tests production monitoring correctness - critical for ops/devops
verifies health endpoint reports correct degraded status when each dependency fails
currently has ZERO test coverage - complete gap in test coverage
proves the system can signal when something is wrong (vs silently failing)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.utils.db import get_db


class TestHealthCheckDependencyFailures:
    """test health endpoint behavior when dependencies fail."""

    def test_all_services_healthy_returns_healthy_status(self, test_client):
        """test that when all dependencies are healthy, status is healthy"""
        # mock all dependencies as healthy
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["db_healthy"] is True
        assert data["redis_healthy"] is True
        assert data["celery_workers_active"] is True

    def test_whisper_not_loaded_returns_degraded(self, test_client):
        """test that when whisper model is not loaded, status is degraded"""
        from src.main import app
        from src.services.whisper_service import get_whisper_service

        mock_whisper = MagicMock()
        mock_whisper.is_loaded = False  # not loaded
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        app.dependency_overrides[get_whisper_service] = lambda: mock_whisper

        with patch("src.main.celery", mock_celery):
            response = test_client.get("/api/v1/health")

        del app.dependency_overrides[get_whisper_service]

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False

    def test_db_connection_failure_returns_degraded(self, test_client, test_db):
        """test that database connection failure returns degraded status"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        # make db.execute raise exception
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("database connection failed")

        from src.main import app

        def override_get_db_fail():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db_fail

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["db_healthy"] is False

    def test_redis_ping_failure_returns_degraded(self, test_client):
        """test that redis/broker connection failure returns degraded status"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_broker_conn.ensure_connection.side_effect = Exception(
            "redis connection refused"
        )
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["redis_healthy"] is False

    def test_celery_workers_inactive_returns_degraded(self, test_client):
        """test that when no celery workers are active, status is degraded"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = None  # no workers
        mock_celery.control.inspect.return_value = mock_inspect

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["celery_workers_active"] is False

    def test_celery_workers_empty_dict_returns_degraded(self, test_client):
        """test that empty workers dict returns degraded status"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {}  # empty workers
        mock_celery.control.inspect.return_value = mock_inspect

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["celery_workers_active"] is False

    def test_celery_inspect_exception_returns_degraded(self, test_client):
        """test that celery inspect exception returns degraded status"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_celery.control.inspect.side_effect = Exception("celery inspect failed")

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["celery_workers_active"] is False

    def test_multiple_failures_still_returns_response(self, test_client):
        """test that multiple dependency failures still return valid response"""
        from src.main import app
        from src.services.whisper_service import get_whisper_service

        mock_whisper = MagicMock()
        mock_whisper.is_loaded = False  # failure 1
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_broker_conn.ensure_connection.side_effect = Exception(
            "redis down"
        )  # failure 2
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = None  # failure 3
        mock_celery.control.inspect.return_value = mock_inspect

        app.dependency_overrides[get_whisper_service] = lambda: mock_whisper

        with patch("src.main.celery", mock_celery):
            response = test_client.get("/api/v1/health")

        del app.dependency_overrides[get_whisper_service]

        # should still return 200 with degraded status (not crash)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False
        assert data["redis_healthy"] is False
        assert data["celery_workers_active"] is False

    def test_timestamp_is_current(self, test_client):
        """test that health check returns current timestamp (not cached)"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        before = datetime.now()

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        after = datetime.now()

        data = response.json()
        timestamp = datetime.fromisoformat(
            data["timestamp"].replace("Z", "+00:00").replace("+00:00", "")
        )

        assert before <= timestamp <= after

        # timestamp should be between before and after (within reason)
        # allow some margin for timezone differences
        assert "timestamp" in data
        assert data["timestamp"] is not None

    def test_device_info_included_in_response(self, test_client):
        """test that device info is included in health response"""
        from src.main import app
        from src.services.whisper_service import get_whisper_service

        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cuda:0"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        app.dependency_overrides[get_whisper_service] = lambda: mock_whisper

        with patch("src.main.celery", mock_celery):
            response = test_client.get("/api/v1/health")

        del app.dependency_overrides[get_whisper_service]

        data = response.json()
        assert "device_info" in data
        assert data["device_info"] == "cuda:0"

    def test_health_response_schema_complete(self, test_client):
        """test that health response includes all required fields"""
        mock_whisper = MagicMock()
        mock_whisper.is_loaded = True
        mock_whisper.device = "cpu"

        mock_celery = MagicMock()
        mock_broker_conn = MagicMock()
        mock_celery.broker_connection.return_value = mock_broker_conn
        mock_inspect = MagicMock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_celery.control.inspect.return_value = mock_inspect

        with patch("src.main.get_whisper_service", return_value=mock_whisper):
            with patch("src.main.celery", mock_celery):
                response = test_client.get("/api/v1/health")

        data = response.json()

        # verify all required fields present
        required_fields = [
            "status",
            "timestamp",
            "model_loaded",
            "device_info",
            "db_healthy",
            "redis_healthy",
            "celery_workers_active",
        ]

        for field in required_fields:
            assert field in data, f"missing required field: {field}"
