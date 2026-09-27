import os
from typing import Generator

import pytest

os.environ.setdefault("USER_SERVICE_USE_STUB", "true")
os.environ.setdefault("WORKFLOW_SERVICE_USE_STUB", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# AIレビューはBedrockへの外部呼び出しなので、既定では無効にしてテストを外部依存から切る。
# レビューそのものの挙動はtest_ai_review_service.pyでクライアントをモックして検証する。
os.environ.setdefault("AI_REVIEW_ENABLED", "false")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.api.dependencies import get_db_dependency
from app.models.application import Application  
from app.services import game_master_tokens
from app.services.game_master_tokens import GameState
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


# game-masterの状態(仮想日付・クリア済みの章)は、frontendがgame-masterから取得した署名付き
# スナップショットをX-Game-Stateヘッダで添えてくる。テストでは毎回ヘッダを組み立てなくて済むよう、
# スナップショットの検証を差し替えて、前提章をクリア済みの状態を返す。
# 前提章そのものの検証はgame-master側の責務なのでここでは扱わない。ヘッダの検証自体は
# test_game_master_tokens.pyで確認する。
@pytest.fixture(autouse=True)
def stub_game_state(monkeypatch) -> None:
    monkeypatch.setattr(
        game_master_tokens,
        "verify_game_state",
        lambda *args, **kwargs: GameState(
            company_id="1",
            # 仮想時間は進めない
            virtual_date_offset_days=0,
            cleared_chapters=list(PROMOTION_PREREQUISITE_CHAPTERS),
        ),
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


