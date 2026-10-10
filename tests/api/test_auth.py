import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

TEST_SECRET = "test-auth-secret-with-at-least-32-bytes"


class AuthenticationEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret_patch = patch.dict(
            "os.environ",
            {"JWT_SECRET_KEY": TEST_SECRET},
        )
        self.secret_patch.start()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.startup_patch = patch("app.main.create_db_and_tables")
        self.startup_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        self.startup_patch.stop()
        self.engine.dispose()
        self.secret_patch.stop()

    def register_and_login(self) -> str:
        response = self.client.post(
            "/auth/register",
            json={
                "email": "rahul@example.com",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(response.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={
                "email": "rahul@example.com",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(login.status_code, 200)
        return login.json()["access_token"]

    def test_registration_stores_hash_and_never_returns_it(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "email": "rahul@example.com",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "rahul@example.com")
        self.assertNotIn("password", response.json())
        self.assertNotIn("password_hash", response.json())
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="rahul@example.com").one()
        self.assertNotEqual(user.password_hash, "secure-password-123")
        self.assertTrue(verify_password("secure-password-123", user.password_hash))
        self.assertTrue(user.password_hash.startswith("$argon2"))

    def test_login_returns_bearer_token_and_token_authenticates(self) -> None:
        token = self.register_and_login()

        response = self.client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "rahul@example.com")
        self.assertNotIn("password_hash", response.json())

    def test_openapi_declares_http_bearer_for_protected_routes(self) -> None:
        schema = self.client.get("/openapi.json").json()

        self.assertEqual(
            schema["components"]["securitySchemes"]["HTTPBearer"],
            {"type": "http", "scheme": "bearer"},
        )
        protected_operations = [
            schema["paths"]["/auth/me"]["get"],
            schema["paths"]["/ai/ask"]["post"],
            schema["paths"]["/students"]["post"],
            schema["paths"]["/students"]["get"],
            schema["paths"]["/students/{student_id}"]["get"],
            schema["paths"]["/students/{student_id}"]["put"],
            schema["paths"]["/students/{student_id}"]["delete"],
        ]
        for operation in protected_operations:
            with self.subTest(operation=operation["operationId"]):
                self.assertEqual(operation["security"], [{"HTTPBearer": []}])

        self.assertNotIn(
            "OAuth2PasswordBearer",
            schema["components"]["securitySchemes"],
        )

    def test_invalid_credentials_are_rejected(self) -> None:
        self.register_and_login()

        response = self.client.post(
            "/auth/login",
            json={
                "email": "rahul@example.com",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

    def test_write_endpoints_require_a_valid_token(self) -> None:
        self.assertEqual(
            self.client.post("/students", json={"name": "No Token"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.put(
                "/students/1",
                json={"name": "No Token"},
            ).status_code,
            401,
        )
        self.assertEqual(self.client.delete("/students/1").status_code, 401)

        token = self.register_and_login()
        create = self.client.post(
            "/students",
            json={"name": "Authorized Student"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(create.status_code, 201)
        self.assertEqual(
            self.client.get(
                "/students",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            200,
        )

    def test_invalid_and_expired_tokens_are_rejected(self) -> None:
        expired = jwt.encode(
            {
                "sub": "1",
                "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            TEST_SECRET,
            algorithm="HS256",
        )
        for token in ("not-a-jwt", expired):
            with self.subTest(token=token[:10]):
                response = self.client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status_code, 401)

    def test_registration_rejects_invalid_credentials_and_duplicate_email(self) -> None:
        short_password = self.client.post(
            "/auth/register",
            json={"email": "rahul@example.com", "password": "short"},
        )
        self.assertEqual(short_password.status_code, 422)

        self.register_and_login()
        duplicate = self.client.post(
            "/auth/register",
            json={
                "email": "RAHUL@example.com",
                "password": "another-secure-password",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
