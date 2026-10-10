import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_endpoint_returns_api_status(self) -> None:
        with patch.dict(
            "os.environ",
            {"JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes"},
        ):
            with patch("app.main.create_db_and_tables"):
                with TestClient(app) as client:
                    response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "message": "Student CRUD AI API is running",
            },
        )
