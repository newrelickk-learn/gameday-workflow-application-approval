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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


