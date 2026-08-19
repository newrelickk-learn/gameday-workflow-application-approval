import base64
import json
import logging
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)

_ENC_FILE = Path(__file__).resolve().parent.parent / "data" / "chapter2_answer.enc.json"


class Chapter2AnswerService:
    """
    第2章（申請書一覧のN+1）の正解判定サービス

    正解テキストはリポジトリにAES-256-GCMで暗号化して保存されており（chapter2_answer.enc.json）、
    復号鍵（CHAPTER2_ANSWER_KEY環境変数、GitHub Secretからk8s Secret経由で注入）は
    このサービスのコンテナ内にしか存在しない。フロントエンドには平文の正解を一切送らず、
    参加者が選んだ選択肢のテキストをこのサービスに送って一致するかどうかだけを判定する。
    """

    _cached_answer: Optional[str] = None

    @classmethod
    def _decrypt_answer(cls) -> Optional[str]:
        if cls._cached_answer is not None:
            return cls._cached_answer

        if not settings.chapter2_answer_key:
            logger.error("Chapter2AnswerService: CHAPTER2_ANSWER_KEYが設定されていません")
            return None

        try:
            with open(_ENC_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)

            key = base64.b64decode(settings.chapter2_answer_key)
            nonce = base64.b64decode(payload["nonce_base64"])
            ciphertext = base64.b64decode(payload["ciphertext_base64"])

            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            cls._cached_answer = plaintext.decode("utf-8")
            return cls._cached_answer
        except Exception as e:
            logger.error("Chapter2AnswerService: 正解の復号に失敗しました: %s", e)
            return None

    @classmethod
    def check_answer(cls, submitted_text: str) -> bool:
        """参加者が選んだ選択肢のテキストが正解と一致するかを判定します"""
        answer = cls._decrypt_answer()
        if answer is None:
            return False
        return submitted_text.strip() == answer.strip()
