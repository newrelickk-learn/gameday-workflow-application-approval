"""裏クエストのクリア引換券(HMAC署名付きトークン)の発行。

裏クエストは「申請が成立したこと」自体が達成条件だが、ここからgame-masterを直接呼ぶと
申請のトレースにgame-masterが混ざってしまう。そこで申請レスポンスに署名付きトークンだけを
載せ、ブラウザがそれを持ってgame-masterへクリアを記録しに行く形にしている。

署名鍵はサービス間通信で既に共有しているgame_master_service_api_key(=game-master側の
INTERNAL_API_KEY)を流用する。署名が無いとブラウザから任意の章を「クリアした」と
申告できてしまうため、鍵が未設定の場合はトークンを発行しない。
"""

from typing import Optional
import base64
import hmac
import hashlib
import json
import logging
import time

from app.core.config import settings
from app.models.application import ApplicationType

logger = logging.getLogger(__name__)

# 裏クエストの章番号。メインストリーム(0〜5)と衝突しないよう101番台を使う。
HIDDEN_QUEST_EXPENSE = 101
HIDDEN_QUEST_BUSINESS_TRIP = 102
# ランブックの暫定対応を自分の会社に適用できたら達成
HIDDEN_QUEST_APPROVED_LIST_REMEDIATION = 103

HIDDEN_QUEST_BY_APPLICATION_TYPE = {
    # 上長を設定したうえで経費申請を出せたら達成
    ApplicationType.EXPENSE.value: HIDDEN_QUEST_EXPENSE,
    # AIレビューを通過して国内出張申請を出せたら達成
    ApplicationType.BUSINESS_TRIP.value: HIDDEN_QUEST_BUSINESS_TRIP,
}

TOKEN_TTL_SECONDS = 300


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def issue(company_id: str, chapter: int, ttl_seconds: int = TOKEN_TTL_SECONDS) -> Optional[str]:
    key = settings.game_master_service_api_key or ""
    if not key:
        logger.warning("hidden_quest_token: 署名鍵が未設定のためトークンを発行しません")
        return None

    payload = json.dumps(
        {"companyId": str(company_id), "chapter": chapter, "exp": int(time.time()) + ttl_seconds},
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    payload_b64 = _base64url_encode(payload)
    signature = hmac.new(key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()

    return f"{payload_b64}.{_base64url_encode(signature)}"


def issue_for_application_type(company_id: Optional[str], application_type: str) -> Optional[str]:
    """申請タイプに対応する裏クエストがあればトークンを発行する。"""
    if company_id is None:
        return None

    chapter = HIDDEN_QUEST_BY_APPLICATION_TYPE.get(application_type)
    if chapter is None:
        return None

    return issue(str(company_id), chapter)
