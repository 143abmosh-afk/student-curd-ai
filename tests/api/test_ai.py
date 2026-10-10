import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.integrations.ollama.client import OllamaUnavailableError
from app.main import app
from app.models.student import Student


class StudentAssistantEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret_patch = patch.dict(
            "os.environ",
            {"JWT_SECRET_KEY": "test-ai-secret-with-at-least-32-bytes"},
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
        registration = self.client.post(
            "/auth/register",
            json={
                "email": "ai-test@example.com",
                "password": "test-password-123",
            },
        )
        if registration.status_code != 201:
            raise AssertionError("Test user registration failed.")
        login = self.client.post(
            "/auth/login",
            json={
                "email": "ai-test@example.com",
                "password": "test-password-123",
            },
        )
        if login.status_code != 200:
            raise AssertionError("Test user login failed.")
        self.client.headers["Authorization"] = (
            f"Bearer {login.json()['access_token']}"
        )

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        self.startup_patch.stop()
        self.secret_patch.stop()
        self.engine.dispose()

    def test_total_count_uses_aggregates_without_exposing_personal_data(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(
                        name="Private Name One",
                        email="private.one@example.com",
                        course="Biology",
                    ),
                    Student(
                        name="Private Name Two",
                        email="private.two@example.com",
                        course="Biology",
                    ),
                ]
            )
            db.commit()

        with patch(
            "app.integrations.ollama.client.generate",
            return_value='{"intent":"total_students","course":null}',
        ) as generate:
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many students are there?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"answer": "There are 2 students in the database."},
        )
        self.assertNotIn("Private Name", response.text)
        self.assertNotIn("private.", response.text)
        generate.assert_called_once()
        self.assertNotIn("private.", generate.call_args.args[0])

    def test_count_by_course_is_case_insensitive(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(name="Student One", course="Computer Science"),
                    Student(name="Student Two", course="Computer Science"),
                    Student(name="Student Three", course="Biology"),
                ]
            )
            db.commit()

        with patch(
            "app.integrations.ollama.client.generate",
            return_value=(
                '{"intent":"count_by_course","course":"computer science"}'
            ),
        ):
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many are taking computer science?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"],
            "There are 2 students enrolled in computer science.",
        )

    def test_singular_course_count_uses_singular_noun(self) -> None:
        with Session(self.engine) as db:
            db.add(Student(name="Student One", course="Biology"))
            db.commit()

        with patch(
            "app.integrations.ollama.client.generate",
            return_value='{"intent":"count_by_course","course":"Biology"}',
        ):
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many are taking Biology?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"],
            "There is 1 student enrolled in Biology.",
        )

    def test_course_summary_is_limited_to_twenty_rows(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [Student(name=f"Student {i}", course=f"Course {i:02}") for i in range(25)]
            )
            db.commit()

        with patch(
            "app.integrations.ollama.client.generate",
            return_value='{"intent":"course_counts","course":null}',
        ):
            response = self.client.post(
                "/ai/ask",
                json={"question": "Show me student counts by course."},
            )

        self.assertEqual(response.status_code, 200)
        answer = response.json()["answer"]
        self.assertIn("Course 00: 1", answer)
        self.assertIn("Course 19: 1", answer)
        self.assertNotIn("Course 20", answer)
        self.assertNotIn("Course 24", answer)

    def test_unsupported_question_is_rejected(self) -> None:
        with patch(
            "app.integrations.ollama.client.generate",
            return_value='{"intent":"unsupported","course":null}',
        ) as generate:
            response = self.client.post(
                "/ai/ask",
                json={"question": "Tell me students' personal details."},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("aggregate questions", response.json()["detail"])
        generate.assert_called_once()

    def test_endpoint_requires_authentication(self) -> None:
        self.client.headers.pop("Authorization")
        with patch("app.integrations.ollama.client.generate") as generate:
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many students are there?"},
            )

        self.assertEqual(response.status_code, 401)
        generate.assert_not_called()

    def test_ollama_unavailable_returns_service_unavailable(self) -> None:
        with patch(
            "app.integrations.ollama.client.generate",
            side_effect=OllamaUnavailableError("connection refused"),
        ):
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many students are there?"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "The local AI assistant is unavailable. Please try again later.",
        )

    def test_invalid_question_plan_returns_bad_gateway(self) -> None:
        with patch(
            "app.integrations.ollama.client.generate",
            return_value='{"intent":"drop_table","course":null}',
        ):
            response = self.client.post(
                "/ai/ask",
                json={"question": "How many students are there?"},
            )

        self.assertEqual(response.status_code, 502)

    def test_question_length_is_validated(self) -> None:
        response = self.client.post("/ai/ask", json={"question": "x" * 501})

        self.assertEqual(response.status_code, 422)

    def test_whitespace_only_question_is_rejected(self) -> None:
        response = self.client.post("/ai/ask", json={"question": "   "})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
