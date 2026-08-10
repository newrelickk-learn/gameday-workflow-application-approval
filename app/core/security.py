import base64
import json
import logging
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

# .NET JWT の ClaimTypes.NameIdentifier のクレーム名
NAME_IDENTIFIER_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"


def _decode_jwt_payload_unsafe(token: str) -> Optional[dict]:
    """
    署名検証を行わずに JWT の payload 部分だけをデコードする。
    python-jose の jwt.decode(token, options=...) は第2引数が key のため誤用されやすいため、
    実JWT（User サービス発行）を確実に読むために使用する。
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return None


def _user_id_from_payload(payload: dict) -> Optional[str]:
    """payload から user_id を取得（.NET / 各種クレーム名に対応）"""
    user_id = (
        payload.get(NAME_IDENTIFIER_CLAIM) or
        payload.get("sub") or
        payload.get("user_id") or
        payload.get("id") or
        payload.get("userId")
    )
    if user_id is not None:
        return str(user_id).strip() or None
    return None


def verify_token(token: str) -> dict:
    """
    JWTトークンを検証し、ユーザーIDを取得します。
    実JWT（3部分形式）の場合は payload を署名検証なしでデコードして user_id を取得します。
    スタブ用の mock-jwt-token-*, user-*, test-user-* 形式も対応します。
    """
    # スタブ/テスト用トークン形式
    if token.startswith("mock-jwt-token-") or token.startswith("user-") or token.startswith("test-user-"):
        user_id = _fallback_user_id_from_token(token)
        user_id = _normalize_user_id(user_id)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_TOKEN", "message": "トークンからユーザーを特定できませんでした"},
            )
        return {"sub": user_id, "user_id": user_id}

    # 実JWT: payload のみデコード（署名検証は別途必要に応じて実装）
    payload = _decode_jwt_payload_unsafe(token)
    if payload is not None:
        user_id = _user_id_from_payload(payload)
        if user_id:
            return {"sub": user_id, "user_id": user_id}
        logger.warning("JWT payload に user_id に相当するクレームがありません: keys=%s", list(payload.keys()))

    # 従来の jose.decode を試す（key が必要なため署名検証する場合）
    try:
        # 署名検証する場合は settings の secret を使用（User サービスと共有時）
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = _user_id_from_payload(payload)
        if user_id:
            return {"sub": user_id, "user_id": user_id}
    except JWTError:
        pass
    except Exception as e:
        logger.debug("jwt.decode 失敗: %s", e)

    # ここに来る = user_id が取れなかった → デフォルトの 28151 は使わず 401 とする
    logger.warning("トークンからユーザーIDを取得できませんでした（デフォルトユーザーは返しません）")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "INVALID_TOKEN", "message": "トークンからユーザーを特定できませんでした"},
    )


def _normalize_user_id(value: Optional[str]) -> str:
    """user_id を常に str に正規化（数値で来る場合に対応）"""
    if value is None:
        return ""
    return str(value).strip()


def _fallback_user_id_from_token(token: str) -> str:
    """スタブ/テスト用トークンからユーザーIDを抽出"""
    if token.startswith("mock-jwt-token-"):
        return token.replace("mock-jwt-token-", "")
    if token.startswith("user-"):
        return token.replace("user-", "")
    if token.startswith("test-user-"):
        return token.replace("test-user-", "")
    return ""


def get_current_user(token: str) -> dict:
    """現在のユーザー情報を取得します"""
    return verify_token(token)

