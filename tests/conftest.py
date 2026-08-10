"""
pytest 共通フィクスチャ。
テスト用 DB（SQLite メモリ）とスタブ有効化を設定し、TestClient を提供します。
"""
import os
from typing import Generator

import pytest

# アプリ import 前に環境変数を設定（スタブ使用・テスト用DB）
os.environ.setdefault("USER_SERVICE_USE_STUB", "true")
os.environ.setdefault("WORKFLOW_SERVICE_USE_STUB", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.api.dependencies import get_db_dependency
from app.models.application import Application  # noqa: F401 - テーブルを Base.metadata に登録

# SQLite 用にテーブル作成（app の engine がすでに settings で作られているので、
# テスト用に別 engine を使い dependency override で差し替える）
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=_test_engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def get_test_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# テスト用 DB を注入
app.dependency_overrides[get_db_dependency] = get_test_db


def auth_headers(user_id: str) -> dict:
    """スタブトークン形式で Authorization ヘッダーを返す。user_id は '28151', '21051' など。"""
    token = f"user-{user_id}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# 他シナリオと揃えたユーザーID
ENGINEER_USER_ID = "28151"
MANAGER_USER_ID = "21051"
DIRECTOR_USER_ID = "1051"
ACCOUNTING_USER_ID = "16051"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


