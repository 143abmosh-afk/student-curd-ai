from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.students import router as students_router

router = APIRouter()
router.include_router(ai_router)
router.include_router(auth_router)
router.include_router(students_router)
