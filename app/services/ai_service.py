import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.integrations.ollama import client as ollama_client
from app.repositories import student_repository
from app.schemas.ai import StudentQuestionPlan

COURSE_RESULTS_LIMIT = 20
PROMPT_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "integrations"
    / "ollama"
    / "prompts"
    / "student_qa.txt"
).read_text(encoding="utf-8")


class UnsupportedQuestionError(Exception):
    pass


class InvalidQuestionPlanError(Exception):
    pass


def answer_student_question(db: Session, question: str) -> str:
    prompt = PROMPT_TEMPLATE.format(question=question)
    try:
        plan_data = json.loads(ollama_client.generate(prompt))
        plan = StudentQuestionPlan.model_validate(plan_data)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise InvalidQuestionPlanError(
            "The assistant could not interpret the question safely."
        ) from exc

    if plan.intent == "unsupported":
        raise UnsupportedQuestionError(
            "I can answer aggregate questions about total student counts "
            "and counts by course, but not identify students or provide "
            "personal details."
        )

    if plan.intent == "total_students":
        total = student_repository.count_students(db)
        return f"{_student_count_phrase(total)} in the database."

    if plan.intent == "count_by_course":
        if plan.course is None or not plan.course.strip():
            raise UnsupportedQuestionError(
                "Please specify a course to count students for."
            )
        count = student_repository.count_students_by_course(
            db,
            plan.course.strip(),
        )
        return (
            f"{_student_count_phrase(count)} enrolled in "
            f"{plan.course.strip()}."
        )

    counts = student_repository.count_students_per_course(
        db,
        limit=COURSE_RESULTS_LIMIT,
    )
    if not counts:
        return "There are no students with a course recorded."
    summary = "; ".join(f"{course}: {count}" for course, count in counts)
    return f"Student counts by course (up to {COURSE_RESULTS_LIMIT} courses): {summary}."


def _student_count_phrase(count: int) -> str:
    if count == 1:
        return "There is 1 student"
    return f"There are {count} students"
