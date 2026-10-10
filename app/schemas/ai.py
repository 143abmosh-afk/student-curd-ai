from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def strip_and_validate_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError(
                "Question must contain at least 3 non-whitespace characters."
            )
        return value


class StudentQuestionResponse(BaseModel):
    answer: str = Field(min_length=1, max_length=6000)


class StudentQuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal[
        "total_students",
        "count_by_course",
        "course_counts",
        "unsupported",
    ]
    course: str | None = Field(default=None, max_length=255)
