import asyncio
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import create_db_and_tables
from app.main import app, lifespan
from app.models.student import Student


class DatabaseSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_initializes_student_table(self) -> None:
        create_db_and_tables(self.engine)

        table_names = inspect(self.engine).get_table_names()
        self.assertIn("students", table_names)
        self.assertIn("users", table_names)

    def test_creates_student_record(self) -> None:
        create_db_and_tables(self.engine)
        student = Student(
            name="Avery Student",
            date_of_birth=date(2005, 4, 12),
            email="avery@example.com",
            course="Computer Science",
        )

        with Session(self.engine) as session:
            session.add(student)
            session.commit()
            session.refresh(student)

            saved_student = session.get(Student, student.student_id)

        self.assertIsNotNone(saved_student)
        self.assertEqual(saved_student.name, "Avery Student")
        self.assertEqual(saved_student.date_of_birth, date(2005, 4, 12))
        self.assertEqual(saved_student.email, "avery@example.com")

    def test_application_startup_initializes_database(self) -> None:
        async def run_lifespan() -> None:
            async with lifespan(app):
                pass

        with patch.dict(
            "os.environ",
            {"JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes"},
        ):
            with patch("app.main.create_db_and_tables") as initialize_database:
                asyncio.run(run_lifespan())

        initialize_database.assert_called_once_with()
