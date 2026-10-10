import unittest
from unittest.mock import patch
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.student import Student


class StudentEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            with Session(self.engine) as db:
                yield db

        self.secret_patch = patch.dict(
            "os.environ",
            {"JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes"},
        )
        self.secret_patch.start()
        app.dependency_overrides[get_db] = override_get_db
        self.startup_patch = patch("app.main.create_db_and_tables")
        self.startup_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        registration = self.client.post(
            "/auth/register",
            json={
                "email": "student-api-test@example.com",
                "password": "test-password-123",
            },
        )
        if registration.status_code != 201:
            raise AssertionError("Test user registration failed.")
        login = self.client.post(
            "/auth/login",
            json={
                "email": "student-api-test@example.com",
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

    def test_create_student(self) -> None:
        response = self.client.post(
            "/students",
            json={
                "name": "Avery Student",
                "date_of_birth": "2005-04-12",
                "email": "avery@example.com",
                "course": "Computer Science",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["student_id"], 1)
        self.assertEqual(response.json()["name"], "Avery Student")
        self.assertEqual(response.json()["date_of_birth"], "2005-04-12")

    def test_create_student_accepts_valid_email(self) -> None:
        response = self.client.post(
            "/students",
            json={"name": "Rahul Student", "email": "rahul@gmail.com"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "rahul@gmail.com")

    def test_create_student_rejects_invalid_emails_without_inserting(self) -> None:
        for email in ("invalid-email", "rahul@", "@gmail.com"):
            with self.subTest(email=email):
                response = self.client.post(
                    "/students",
                    json={"name": "Invalid Student", "email": email},
                )

                self.assertEqual(response.status_code, 422)
                self.assertEqual(self.client.get("/students").json(), [])

    def test_list_students(self) -> None:
        with Session(self.engine) as db:
            db.add_all([Student(name="Avery Student"), Student(name="Jordan Student")])
            db.commit()

        response = self.client.get("/students")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [student["name"] for student in response.json()],
            ["Avery Student", "Jordan Student"],
        )

    def test_list_students_requires_authentication(self) -> None:
        self.client.headers.pop("Authorization")

        response = self.client.get("/students")

        self.assertEqual(response.status_code, 401)

    def test_list_students_supports_limit_and_offset(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(name="Avery Student"),
                    Student(name="Jordan Student"),
                    Student(name="Taylor Student"),
                ]
            )
            db.commit()

        response = self.client.get("/students?limit=1&offset=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [student["name"] for student in response.json()],
            ["Jordan Student"],
        )

    def test_list_students_rejects_invalid_pagination(self) -> None:
        for query in ("limit=0", "limit=501", "offset=-1"):
            with self.subTest(query=query):
                response = self.client.get(f"/students?{query}")
                self.assertEqual(response.status_code, 422)

    def test_search_matches_name_or_email_case_insensitively(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(name="Riya Sharma", email="RIYA@example.com"),
                    Student(name="Other Student", email="contact@example.org"),
                ]
            )
            db.commit()

        name_results = self.client.get("/students?search=RIYA").json()
        email_results = self.client.get("/students?search=EXAMPLE.ORG").json()

        self.assertEqual([student["name"] for student in name_results], ["Riya Sharma"])
        self.assertEqual([student["name"] for student in email_results], ["Other Student"])

    def test_course_and_address_filters_are_case_insensitive(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(
                        name="Riya Sharma",
                        course="Computer Science",
                        address="North Campus, Block A",
                    ),
                    Student(
                        name="Aman Patel",
                        course="Mathematics",
                        address="South Campus",
                    ),
                ]
            )
            db.commit()

        response = self.client.get(
            "/students?course=computer&address=NORTH CAMPUS"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [student["name"] for student in response.json()],
            ["Riya Sharma"],
        )

    def test_students_can_be_sorted_ascending_and_descending(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(name="Zara", enrollment_date=date(2024, 1, 1)),
                    Student(name="Aman", enrollment_date=date(2023, 1, 1)),
                    Student(name="Mina", enrollment_date=date(2025, 1, 1)),
                ]
            )
            db.commit()

        by_name = self.client.get("/students?sort_by=name&sort_order=asc").json()
        by_enrollment_desc = self.client.get(
            "/students?sort_by=enrollment_date&sort_order=desc"
        ).json()
        by_id_desc = self.client.get(
            "/students?sort_by=student_id&sort_order=desc"
        ).json()

        self.assertEqual([student["name"] for student in by_name], ["Aman", "Mina", "Zara"])
        self.assertEqual(
            [student["name"] for student in by_enrollment_desc],
            ["Mina", "Zara", "Aman"],
        )
        self.assertEqual(
            [student["student_id"] for student in by_id_desc],
            [3, 2, 1],
        )

    def test_search_and_sort_combine_with_pagination(self) -> None:
        with Session(self.engine) as db:
            db.add_all(
                [
                    Student(name="Ari One", course="Computer Science"),
                    Student(name="Ari Two", course="Computer Science"),
                    Student(name="Ari Three", course="Computer Science"),
                    Student(name="Bea Four", course="Mathematics"),
                ]
            )
            db.commit()

        response = self.client.get(
            "/students?search=ARI&course=computer&sort_by=name"
            "&sort_order=desc&limit=1&offset=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([student["name"] for student in response.json()], ["Ari Three"])

    def test_list_students_rejects_invalid_search_and_sort_parameters(self) -> None:
        for query in (
            "search=",
            "sort_by=email",
            "sort_order=sideways",
        ):
            with self.subTest(query=query):
                response = self.client.get(f"/students?{query}")
                self.assertEqual(response.status_code, 422)

    def test_get_student_by_id(self) -> None:
        with Session(self.engine) as db:
            student = Student(name="Avery Student")
            db.add(student)
            db.commit()
            student_id = student.student_id

        response = self.client.get(f"/students/{student_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["student_id"], student_id)
        self.assertEqual(response.json()["name"], "Avery Student")

    def test_get_student_by_id_requires_authentication(self) -> None:
        self.client.headers.pop("Authorization")

        response = self.client.get("/students/1")

        self.assertEqual(response.status_code, 401)

    def test_get_missing_student_returns_404(self) -> None:
        response = self.client.get("/students/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Student not found.")

    def test_duplicate_email_returns_409(self) -> None:
        payload = {"name": "Avery Student", "email": "avery@example.com"}
        first_response = self.client.post("/students", json=payload)
        duplicate_response = self.client.post("/students", json=payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(duplicate_response.status_code, 409)

    def test_update_student(self) -> None:
        create_response = self.client.post(
            "/students",
            json={"name": "Avery Student", "course": "Mathematics"},
        )
        student_id = create_response.json()["student_id"]

        response = self.client.put(
            f"/students/{student_id}",
            json={
                "name": "Avery Updated",
                "date_of_birth": "2005-04-12",
                "email": "avery@example.com",
                "course": "Computer Science",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["student_id"], student_id)
        self.assertEqual(response.json()["name"], "Avery Updated")
        self.assertEqual(response.json()["date_of_birth"], "2005-04-12")
        self.assertEqual(response.json()["course"], "Computer Science")

    def test_update_missing_student_returns_404(self) -> None:
        response = self.client.put(
            "/students/999",
            json={"name": "Avery Updated"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Student not found.")

    def test_update_student_validates_request_body(self) -> None:
        response = self.client.put(
            "/students/1",
            json={"name": "", "date_of_birth": "not-a-date"},
        )

        self.assertEqual(response.status_code, 422)

    def test_delete_student(self) -> None:
        create_response = self.client.post(
            "/students",
            json={"name": "Avery Student"},
        )
        student_id = create_response.json()["student_id"]

        response = self.client.delete(f"/students/{student_id}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(
            self.client.get(f"/students/{student_id}").status_code,
            404,
        )

    def test_delete_missing_student_returns_404(self) -> None:
        response = self.client.delete("/students/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Student not found.")
