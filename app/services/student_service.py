from typing import Literal

from sqlalchemy.orm import Session

from app.models.student import Student
from app.repositories import student_repository
from app.schemas.student import StudentCreate, StudentUpdate


def create_student(db: Session, student_data: StudentCreate) -> Student:
    return student_repository.create_student(db, student_data)


def list_students(
    db: Session,
    *,
    search: str | None,
    course: str | None,
    address: str | None,
    sort_by: Literal["student_id", "name", "enrollment_date"],
    sort_order: Literal["asc", "desc"],
    limit: int,
    offset: int,
) -> list[Student]:
    return student_repository.list_students(
        db,
        search=search,
        course=course,
        address=address,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


def get_student(db: Session, student_id: int) -> Student | None:
    return student_repository.get_student(db, student_id)


def update_student(
    db: Session,
    student: Student,
    student_data: StudentUpdate,
) -> Student:
    return student_repository.update_student(db, student, student_data)


def delete_student(db: Session, student: Student) -> None:
    student_repository.delete_student(db, student)
