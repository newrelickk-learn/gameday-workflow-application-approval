"""申請の成立と裏クエスト・AIレビューの結びつき。

裏クエストのクリアはこのサービスからgame-masterを呼ばず、レスポンスに載せた署名付き
トークンをブラウザが持って行く。そのトークンが申請レスポンスに乗ることを確認する。
"""

from datetime import date, timedelta

from app.core.config import settings
from app.services import hidden_quest_token
import app.services.ai_review_service as ai_review_module
from tests.conftest import ENGINEER_USER_ID, MANAGER_USER_ID, auth_headers
from tests.test_ai_review_service import FakeBedrockClient


def _future_start_end(days_ahead: int = 14, span_days: int = 3):
    start = date.today() + timedelta(days=days_ahead)
    end = start + timedelta(days=span_days - 1)
    return start.isoformat(), end.isoformat()


def _business_trip_payload(description: str) -> dict:
    start, end = _future_start_end(14, 3)
    return {
        "type": "business-trip",
        "title": "札幌支社訪問",
        "description": description,
        "startDate": start,
        "endDate": end,
        "days": 3,
        "applicantId": ENGINEER_USER_ID,
    }


def test_expense_application_returns_a_hidden_quest_token(client):
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "expense",
            "title": "交通費精算",
            "description": "出張時の交通費",
            "amount": 50000,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )

    assert resp.status_code == 201
    tokens = resp.json().get("hiddenQuestTokens")
    assert tokens and len(tokens) == 1


def test_expense_application_by_a_manager_returns_no_hidden_quest_token(client):
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "expense",
            "title": "交通費精算",
            "description": "出張時の交通費",
            "amount": 50000,
            "applicantId": MANAGER_USER_ID,
        },
        headers=auth_headers(MANAGER_USER_ID),
    )

    assert resp.status_code == 201
    assert resp.json().get("hiddenQuestTokens") is None


def test_vacation_application_returns_no_hidden_quest_token(client):
    start, end = _future_start_end(7, 2)
    resp = client.post(
        "/api/v1/applications",
        json={
            "type": "vacation",
            "title": "有給休暇申請",
            "description": "私用のため",
            "startDate": start,
            "endDate": end,
            "days": 2,
            "applicantId": ENGINEER_USER_ID,
        },
        headers=auth_headers(ENGINEER_USER_ID),
    )

    assert resp.status_code == 201
    assert resp.json().get("hiddenQuestTokens") is None


def test_business_trip_rejected_by_ai_review_is_not_created(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_review_enabled", True)
    monkeypatch.setattr(
        ai_review_module,
        "_get_client",
        lambda: FakeBedrockClient(text='{"approved": false, "reason": "訪問先を追記してください。"}'),
    )

    resp = client.post(
        "/api/v1/applications",
        json=_business_trip_payload("行きます"),
        headers=auth_headers(ENGINEER_USER_ID),
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["error"] == "AI_REVIEW_REJECTED"
    assert detail["field"] == "description"
    assert detail["message"] == "訪問先を追記してください。"


def test_business_trip_approved_by_ai_review_returns_a_hidden_quest_token(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_review_enabled", True)
    monkeypatch.setattr(
        ai_review_module,
        "_get_client",
        lambda: FakeBedrockClient(text='{"approved": true, "reason": ""}'),
    )

    resp = client.post(
        "/api/v1/applications",
        json=_business_trip_payload(
            "札幌支社で新システムの移行計画について、先方の情報システム部と3日間の打ち合わせを行います。"
        ),
        headers=auth_headers(ENGINEER_USER_ID),
    )

    assert resp.status_code == 201
    tokens = resp.json().get("hiddenQuestTokens")
    assert tokens and len(tokens) == 1
    assert hidden_quest_token.HIDDEN_QUEST_BUSINESS_TRIP == _chapter_of(tokens[0])


def _chapter_of(token: str) -> int:
    import base64
    import json

    payload_b64 = token.split(".")[0]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))["chapter"]
