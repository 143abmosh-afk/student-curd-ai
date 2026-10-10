from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.integrations.ollama.client import (
    OllamaResponseError,
    OllamaUnavailableError,
)
from app.models.user import User
from app.schemas.ai import StudentQuestion, StudentQuestionResponse
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI assistant"])


@router.post("/ask", response_model=StudentQuestionResponse)
def ask_student_question(
    request: StudentQuestion,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> StudentQuestionResponse:
    try:
        answer = ai_service.answer_student_question(db, request.question)
    except ai_service.UnsupportedQuestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except OllamaUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local AI assistant is unavailable. Please try again later.",
        ) from exc
    except (OllamaResponseError, ai_service.InvalidQuestionPlanError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The local AI assistant returned an invalid response.",
        ) from exc
    return StudentQuestionResponse(answer=answer)
