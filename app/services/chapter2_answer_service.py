import base64
import json
import logging
import random
from pathlib import Path
from typing import List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ANSWER_FILE = _DATA_DIR / "chapter2_answer.enc.json"
_OPTIONS_FILE = _DATA_DIR / "chapter2_options.enc.json"


class Chapter2AnswerService:
    """
    第2章（申請書一覧のN+1）の原因診断ドロップダウン向けサービス

    正解テキストと選択肢100件は、いずれもリポジトリにAES-256-GCMで暗号化して
    保存されており（chapter2_answer.enc.json / chapter2_options.enc.json）、
    復号鍵（CHAPTER2_ANSWER_KEY環境変数、GitHub Secretからk8s Secret経由で注入）は
    このサービスのコンテナ内にしか存在しない。選択肢はダッシュボード表示のために
    復号して返す必要があるが、どれが正解かはレスポンスに含めない
    （正解判定は選択されたテキストとの一致判定のみで行う）。
    """

    _cached_answer: Optional[str] = None
    _cached_options: Optional[List[str]] = None

    @classmethod
    def _decrypt_file(cls, path: Path) -> Optional[bytes]:
        if not settings.chapter2_answer_key:
            logger.error("Chapter2AnswerService: CHAPTER2_ANSWER_KEYが設定されていません")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            key = base64.b64decode(settings.chapter2_answer_key)
            nonce = base64.b64decode(payload["nonce_base64"])
            ciphertext = base64.b64decode(payload["ciphertext_base64"])

            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            logger.error("Chapter2AnswerService: %sの復号に失敗しました: %s", path.name, e)
            return None

    @classmethod
    def _decrypt_answer(cls) -> Optional[str]:
        if cls._cached_answer is not None:
            return cls._cached_answer
        plaintext = cls._decrypt_file(_ANSWER_FILE)
        if plaintext is None:
            return None
        cls._cached_answer = plaintext.decode("utf-8")
        return cls._cached_answer

    @classmethod
    def _decrypt_options(cls) -> Optional[List[str]]:
        if cls._cached_options is not None:
            return cls._cached_options
        plaintext = cls._decrypt_file(_OPTIONS_FILE)
        if plaintext is None:
            return None
        cls._cached_options = json.loads(plaintext.decode("utf-8"))
        return cls._cached_options

    @classmethod
    def get_shuffled_options(cls) -> List[str]:
        """
        選択肢100件を復号し、リクエストごとにシャッフルして返します

        （常に同じ並び順だと、正解の位置を覚えてしまい暗記で突破できてしまうため）
        """
        options = cls._decrypt_options()
        if options is None:
            return []
        shuffled = list(options)
        random.shuffle(shuffled)
        return shuffled

    @classmethod
    def check_answer(cls, submitted_text: str) -> bool:
        """参加者が選んだ選択肢のテキストが正解と一致するかを判定します"""
        answer = cls._decrypt_answer()
        if answer is None:
            return False
        return submitted_text.strip() == answer.strip()
