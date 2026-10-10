from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.core.config import load_environment
from app.api.router import router as api_router
from app.core.security import validate_auth_configuration
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    load_environment()
    validate_auth_configuration()
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "message": "Student CRUD AI API is running",
    }
