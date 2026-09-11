import os
from typing import Generator

import pytest

os.environ.setdefault("USER_SERVICE_USE_STUB", "true")
os.environ.setdefault("WORKFLOW_SERVICE_USE_STUB", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.api.dependencies import get_db_dependency
from app.models.application import Application  
from app.services.game_master_client import GameMasterClient
from app.services.validation_service import PROMOTION_PREREQUISITE_CHAPTERS

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_test_engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def get_test_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_dependency] = get_test_db


def auth_headers(user_id: str) -> dict:
    token = f"user-{user_id}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


ENGINEER_USER_ID = "28151"
MANAGER_USER_ID = "21051"
DIRECTOR_USER_ID = "1051"
ACCOUNTING_USER_ID = "16051"


# game-masterは別サービスとして疎結合に切り出されており、テスト環境にはそのホストが
# 存在しない(k8sのサービス名なのでDNSで引けない)。素のままだと全ての呼び出しが
# 名前解決エラーになり、プロモーション申請が「前提章が未クリア」と判定されて400になる。
# ここで差し替えて、テストからはgame-masterへのHTTPを一切出さないようにする。
@pytest.fixture(autouse=True)
def stub_game_master(monkeypatch) -> None:
    # 仮想時間は進めない(game-master不在時の実装と同じNone)
    monkeypatch.setattr(GameMasterClient, "get_game_progress", lambda *args, **kwargs: None)
    # 前提章の判定でapproval側のテストが止まらないよう、必要な章はクリア済みとして返す。
    # 前提章そのものの検証はgame-master側の責務なのでここでは扱わない。
    monkeypatch.setattr(
        GameMasterClient,
        "get_cleared_chapters_today",
        lambda *args, **kwargs: list(PROMOTION_PREREQUISITE_CHAPTERS),
    )
    # 進捗の記録系は何もせず成功扱いにする
    monkeypatch.setattr(GameMasterClient, "mark_chapter_cleared", lambda *args, **kwargs: True)
    monkeypatch.setattr(GameMasterClient, "mark_chapter_incorrect", lambda *args, **kwargs: True)
    monkeypatch.setattr(GameMasterClient, "apply_approved_application", lambda *args, **kwargs: None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


