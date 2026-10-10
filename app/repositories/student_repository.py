from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


def create_student(db: Session, student_data: StudentCreate) -> Student:
    student = Student(**student_data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


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
    statement = select(Student)

    if search is not None:
        search_pattern = _contains_pattern(search)
        statement = statement.where(
            or_(
                Student.name.ilike(search_pattern, escape="\\"),
                Student.email.ilike(search_pattern, escape="\\"),
            )
        )
    if course is not None:
        statement = statement.where(
            Student.course.ilike(_contains_pattern(course), escape="\\")
        )
    if address is not None:
        statement = statement.where(
            Student.address.ilike(_contains_pattern(address), escape="\\")
        )

    sort_column = {
        "student_id": Student.student_id,
        "name": Student.name,
        "enrollment_date": Student.enrollment_date,
    }[sort_by]
    ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    statement = statement.order_by(ordering, Student.student_id.asc())
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def _contains_pattern(value: str) -> str:
    escaped_value = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped_value}%"


def count_students(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Student)) or 0


def count_students_by_course(db: Session, course: str) -> int:
    statement = select(func.count()).select_from(Student).where(
        func.lower(Student.course) == course.casefold()
    )
    return db.scalar(statement) or 0


def count_students_per_course(db: Session, limit: int) -> list[tuple[str, int]]:
    statement = (
        select(Student.course, func.count(Student.student_id).label("student_count"))
        .where(Student.course.is_not(None))
        .group_by(Student.course)
        .order_by(func.count(Student.student_id).desc(), Student.course.asc())
        .limit(limit)
    )
    return [
        (course, count)
        for course, count in db.execute(statement)
        if course is not None
    ]


def get_student(db: Session, student_id: int) -> Student | None:
    return db.get(Student, student_id)


def update_student(
    db: Session,
    student: Student,
    student_data: StudentUpdate,
) -> Student:
    for field, value in student_data.model_dump().items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student: Student) -> None:
    db.delete(student)
    db.commit()
