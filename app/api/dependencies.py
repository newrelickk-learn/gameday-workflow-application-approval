from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user

security = HTTPBearer()


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """現在のユーザーを取得する依存関係"""
    token = credentials.credentials
    user_info = get_current_user(token)
    # token情報も含める（外部サービス呼び出し時に使用）
    user_info["_token"] = token
    return user_info


def get_db_dependency() -> Generator[Session, None, None]:
    """データベースセッションを取得する依存関係"""
    yield from get_db()

