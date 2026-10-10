from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories import auth_repository


def register_user(db: Session, email: str, password: str) -> User:
    normalized_email = email.casefold()
    return auth_repository.create_user(
        db,
        normalized_email,
        hash_password(password),
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = auth_repository.get_user_by_email(db, email.casefold())
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def issue_access_token(user: User) -> str:
    return create_access_token(user.user_id)
