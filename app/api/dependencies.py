from typing import Generator
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user

security = HTTPBearer()


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    user_info = get_current_user(token)
    user_info["_token"] = token
    return user_info


def get_db_dependency() -> Generator[Session, None, None]:
    yield from get_db()

