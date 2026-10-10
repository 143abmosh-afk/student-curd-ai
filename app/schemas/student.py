from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    course: str | None = Field(default=None, max_length=255)
    address: str | None = None
    enrollment_date: date | None = None


class StudentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    email: EmailStr | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    course: str | None = Field(default=None, max_length=255)
    address: str | None = None
    enrollment_date: date | None = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: int
    name: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    course: str | None
    address: str | None
    enrollment_date: date | None
