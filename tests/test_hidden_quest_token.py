"""裏クエストのクリア引換券(HMAC署名付きトークン)の発行。

検証側(game-master/PHP)と同じ手順で署名を再計算し、形式が噛み合うことを確認する。
"""

import base64
import hmac
import hashlib
import json
import time

from app.core.config import settings
from app.services import hidden_quest_token


def decode_payload(token: str) -> dict:
    payload_b64 = token.split(".")[0]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def recompute_signature(token: str, key: str) -> str:
    payload_b64 = token.split(".")[0]
    raw = hmac.new(key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_expense_application_by_an_engineer_issues_a_token_for_hidden_quest_1():
    token = hidden_quest_token.issue_for_application_type("1", "expense", "engineer")

    assert token is not None
    assert decode_payload(token)["chapter"] == hidden_quest_token.HIDDEN_QUEST_EXPENSE


def test_expense_application_by_a_manager_does_not_issue_a_token():
    # 上長が未設定のエンジニアが申請できるようになったことが達成条件のため、
    # 最初から上長を持っているマネージャーの申請では達成にしない。
    assert hidden_quest_token.issue_for_application_type("1", "expense", "manager") is None
    assert hidden_quest_token.issue_for_application_type("1", "expense", None) is None


def test_business_trip_application_issues_a_token_regardless_of_role():
    token = hidden_quest_token.issue_for_application_type("1", "business-trip", "manager")

    assert token is not None
    assert decode_payload(token)["chapter"] == hidden_quest_token.HIDDEN_QUEST_BUSINESS_TRIP


def test_other_application_types_do_not_issue_a_token():
    assert hidden_quest_token.issue_for_application_type("1", "vacation", "engineer") is None
    assert hidden_quest_token.issue_for_application_type("1", "promotion", "manager") is None


def test_token_is_signed_with_the_shared_key():
    token = hidden_quest_token.issue("42", hidden_quest_token.HIDDEN_QUEST_EXPENSE)

    assert token is not None
    payload = decode_payload(token)
    assert payload["companyId"] == "42"
    assert payload["exp"] > int(time.time())
    assert token.split(".")[1] == recompute_signature(token, settings.game_master_service_api_key)


def test_no_token_is_issued_without_a_signing_key(monkeypatch):
    # 鍵が無いまま発行すると、ブラウザから任意の章をクリア済みと申告できてしまう
    monkeypatch.setattr(settings, "game_master_service_api_key", "")

    assert hidden_quest_token.issue("1", hidden_quest_token.HIDDEN_QUEST_EXPENSE) is None


def test_no_token_is_issued_without_a_company():
    assert hidden_quest_token.issue_for_application_type(None, "expense", "engineer") is None
