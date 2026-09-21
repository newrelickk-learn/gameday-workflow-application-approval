"""ランブックの暫定対応(承認済み一覧の遅延)の適用API。

原因の切り分け(第2章)が終わるまでは適用できないこと、適用は会社単位で閉じていること、
適用時に裏クエストの引換券が返ることを確認する。
"""

import base64
import json

import pytest

from app.api.v1.endpoints.remediations import INVESTIGATION_CHAPTER
from app.services import hidden_quest_token
from app.services.game_master_client import GameMasterClient
from app.services.remediation_service import RemediationService, FEATURE_APPROVED_LIST_SLOW
from tests.conftest import ENGINEER_USER_ID, MANAGER_USER_ID, auth_headers, TestSessionLocal

ENDPOINT = "/api/v1/remediations/approved-list-slow"


@pytest.fixture
def investigation_done(monkeypatch):
    monkeypatch.setattr(
        GameMasterClient,
        "get_cleared_chapters_today",
        lambda *args, **kwargs: [0, INVESTIGATION_CHAPTER],
    )


@pytest.fixture
def investigation_not_done(monkeypatch):
    monkeypatch.setattr(GameMasterClient, "get_cleared_chapters_today", lambda *args, **kwargs: [0])


@pytest.fixture(autouse=True)
def clean_remediations():
    yield
    db = TestSessionLocal()
    try:
        from app.models.application import CompanyRemediation

        db.query(CompanyRemediation).delete()
        db.commit()
    finally:
        db.close()


def test_cannot_apply_before_the_investigation_is_done(client, investigation_not_done):
    resp = client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))

    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert body["reason"] == "investigation_incomplete"
    assert body["hiddenQuestTokens"] is None


def test_apply_returns_a_hidden_quest_token(client, investigation_done):
    resp = client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))

    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["alreadyApplied"] is False

    tokens = body["hiddenQuestTokens"]
    assert tokens and len(tokens) == 1

    payload_b64 = tokens[0].split(".")[0]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    assert payload["chapter"] == hidden_quest_token.HIDDEN_QUEST_APPROVED_LIST_REMEDIATION


def test_applying_twice_is_idempotent(client, investigation_done):
    client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))
    resp = client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))

    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["alreadyApplied"] is True
    # 2回目は引換券を出さない(既にクリア済みのため)
    assert body["hiddenQuestTokens"] is None


def test_status_endpoint_reflects_application(client, investigation_done):
    before = client.get(ENDPOINT, headers=auth_headers(MANAGER_USER_ID)).json()
    assert before["applied"] is False

    client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))

    after = client.get(ENDPOINT, headers=auth_headers(MANAGER_USER_ID)).json()
    assert after["applied"] is True


def test_remediation_is_scoped_to_a_company():
    db = TestSessionLocal()
    try:
        RemediationService.apply(db, 1, FEATURE_APPROVED_LIST_SLOW)

        assert RemediationService.is_applied(db, 1, FEATURE_APPROVED_LIST_SLOW) is True
        # 他の会社には波及しない
        assert RemediationService.is_applied(db, 2, FEATURE_APPROVED_LIST_SLOW) is False
        # 会社が特定できない場合も適用されていない扱い
        assert RemediationService.is_applied(db, None, FEATURE_APPROVED_LIST_SLOW) is False
    finally:
        db.close()


def test_expired_remediation_is_not_applied():
    from datetime import date, timedelta

    from app.models.application import CompanyRemediation

    db = TestSessionLocal()
    try:
        RemediationService.apply(db, 1, FEATURE_APPROVED_LIST_SLOW)
        row = (
            db.query(CompanyRemediation)
            .filter(CompanyRemediation.company_id == 1)
            .first()
        )
        # 前日に適用した状態にすると、当日分としては無効になる(日次リセット相当)
        row.applied_date = date.today() - timedelta(days=1)
        db.commit()

        assert RemediationService.is_applied(db, 1, FEATURE_APPROVED_LIST_SLOW) is False
    finally:
        db.close()


def test_approved_list_still_works_after_remediation(client, investigation_done):
    client.post(ENDPOINT, headers=auth_headers(MANAGER_USER_ID))

    # 是正後もレスポンスの中身は変わらない(変わるのは読み込み方だけ)
    resp = client.get("/api/v1/applications", headers=auth_headers(ENGINEER_USER_ID))

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
