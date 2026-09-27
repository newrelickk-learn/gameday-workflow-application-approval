"""game-masterを直接呼ばずにfrontend経由でやり取りするためのトークン。

検証側・発行側(game-master/PHP)と同じ形式(`base64url(JSON).base64url(HMAC-SHA256)`)で
噛み合うことと、申請APIがX-Game-Stateヘッダのスナップショットを使うことを確認する。
"""

import base64
import json
import time

from app.services import game_master_tokens, signed_token
from app.services.game_master_tokens import verify_game_state as real_verify_game_state
from app.services.validation_service import PROMOTION_PREREQUISITE_CHAPTERS
from tests.conftest import MANAGER_USER_ID, auth_headers


def decode_payload(token: str) -> dict:
    payload_b64 = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))


def game_state_token(user_id: str, cleared_chapters, exp_offset: int = 60, typ: str = "game-state") -> str:
    return signed_token.sign(
        {
            "typ": typ,
            "userId": user_id,
            "companyId": "1",
            "virtualDateOffsetDays": 3,
            "clearedChapters": cleared_chapters,
            "exp": int(time.time()) + exp_offset,
        }
    )


def test_game_state_snapshot_is_accepted_for_the_same_user():
    state = real_verify_game_state(game_state_token("7", [0, 2]), "7")

    assert state is not None
    assert state.virtual_date_offset_days == 3
    assert state.cleared_chapters == [0, 2]


def test_game_state_snapshot_of_another_user_is_rejected():
    assert real_verify_game_state(game_state_token("7", [0, 2]), "8") is None


def test_expired_or_other_type_of_token_is_not_a_game_state_snapshot():
    assert real_verify_game_state(game_state_token("7", [0], exp_offset=-1), "7") is None
    assert real_verify_game_state(game_state_token("7", [0], typ="approved-application"), "7") is None
    chapter_clear_token = signed_token.sign({"companyId": "1", "chapter": 5, "exp": int(time.time()) + 60})
    assert real_verify_game_state(chapter_clear_token, "7") is None


def test_tampered_game_state_snapshot_is_rejected():
    token = game_state_token("7", [0])
    _, signature = token.split(".")
    forged = base64.urlsafe_b64encode(
        json.dumps({"typ": "game-state", "userId": "7", "companyId": "1", "virtualDateOffsetDays": 0,
                    "clearedChapters": [0, 1, 2, 3, 4], "exp": int(time.time()) + 60}).encode()
    ).decode().rstrip("=")

    assert real_verify_game_state(f"{forged}.{signature}", "7") is None


def test_approved_application_token_carries_what_to_apply():
    token = game_master_tokens.issue_approved_application("1", "business-trip", 2)

    payload = decode_payload(token)
    assert payload["typ"] == "approved-application"
    assert payload["companyId"] == "1"
    assert payload["applicationType"] == "business-trip"
    assert payload["days"] == 2


def promotion_payload() -> dict:
    return {
        "type": "promotion",
        "title": "プロモーション申請",
        "description": "新商品のプロモーション活動",
        "applicantId": MANAGER_USER_ID,
    }


def test_promotion_uses_the_game_state_header_and_returns_a_chapter_clear_token(client, monkeypatch):
    monkeypatch.setattr(game_master_tokens, "verify_game_state", real_verify_game_state)
    headers = {
        **auth_headers(MANAGER_USER_ID),
        game_master_tokens.GAME_STATE_HEADER: game_state_token(
            MANAGER_USER_ID, list(PROMOTION_PREREQUISITE_CHAPTERS)
        ),
    }

    resp = client.post("/api/v1/applications", json=promotion_payload(), headers=headers)

    assert resp.status_code == 201
    tokens = resp.json()["chapterClearTokens"]
    assert len(tokens) == 1
    assert decode_payload(tokens[0])["chapter"] == 5


def test_promotion_without_a_game_state_snapshot_is_treated_as_prerequisites_not_cleared(client, monkeypatch):
    monkeypatch.setattr(game_master_tokens, "verify_game_state", real_verify_game_state)

    resp = client.post("/api/v1/applications", json=promotion_payload(), headers=auth_headers(MANAGER_USER_ID))

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "PREREQUISITE_CHAPTERS_NOT_CLEARED"
