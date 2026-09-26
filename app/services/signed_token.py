"""game-masterとやり取りするHMAC署名付きトークン(`base64url(JSON).base64url(HMAC-SHA256)`)。

このサービスからgame-masterを直接呼ぶと、申請・承認のトレース(サービスマップ)に
game-masterが混ざってしまう。そこでgame-masterに記録してほしいことは署名付きトークンに
してレスポンスに載せ、frontendがgame-masterへ届ける。逆にgame-masterの状態が必要な処理では、
frontendがgame-masterから受け取ったトークンをリクエストに添えてくる。

署名鍵はサービス間通信で既に共有しているgame_master_service_api_key(=game-master側の
INTERNAL_API_KEY)を流用する。形式はgame-master側のSignedTokenServiceと揃えている。
"""

from typing import Any, Dict, Optional
import base64
import hmac
import hashlib
import json
import logging
import time

from app.core.config import settings

logger = logging.getLogger(__name__)


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _base64url_decode(encoded: str) -> bytes:
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))


def _signature(key: str, payload_b64: str) -> str:
    raw = hmac.new(key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _base64url_encode(raw)


def sign(payload: Dict[str, Any]) -> Optional[str]:
    key = settings.game_master_service_api_key or ""
    if not key:
        logger.warning("signed_token: 署名鍵が未設定のためトークンを発行しません")
        return None

    payload_b64 = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    return f"{payload_b64}.{_signature(key, payload_b64)}"


def decode(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """署名と有効期限(exp)を検証し、正当ならペイロードを返す。"""
    key = settings.game_master_service_api_key or ""
    if not key or not token:
        return None

    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, signature_b64 = parts

    if not hmac.compare_digest(_signature(key, payload_b64), signature_b64):
        logger.warning("signed_token: 署名が一致しません")
        return None

    try:
        payload = json.loads(_base64url_decode(payload_b64))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < time.time():
        return None

    return payload
