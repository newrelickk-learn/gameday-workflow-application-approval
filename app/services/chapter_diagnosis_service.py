import base64
import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ChapterDiagnosisService:
    """
    GameDay演習の「New Relicでしか分からない原因を選ばせる」診断ドロップダウン
    （第2章・第4章・第5章など）向けの共通サービス

    章ごとの正解テキストと選択肢は、いずれもリポジトリにAES-256-GCMで暗号化して
    保存されており（app/data/chapter{N}_answer.enc.json / chapter{N}_options.enc.json）、
    復号鍵（CHAPTER_DIAGNOSIS_KEY環境変数、GitHub Secretからk8s Secret経由で注入）は
    このサービスのコンテナ内にしか存在しない。選択肢はダッシュボード表示のために
    復号して返す必要があるが、どれが正解かはレスポンスに含めない
    （正解判定は選択されたテキストとの一致判定のみで行う）。
    """

    _cached_answers: Dict[int, str] = {}
    _cached_options: Dict[int, List[str]] = {}

    @classmethod
    def _decrypt_file(cls, path: Path) -> Optional[bytes]:
        if not settings.chapter_diagnosis_key:
            logger.error("ChapterDiagnosisService: CHAPTER_DIAGNOSIS_KEYが設定されていません")
            return None
        if not path.exists():
            logger.error("ChapterDiagnosisService: %sが存在しません", path)
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            key = base64.b64decode(settings.chapter_diagnosis_key)
            nonce = base64.b64decode(payload["nonce_base64"])
            ciphertext = base64.b64decode(payload["ciphertext_base64"])

            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as e:
            logger.error("ChapterDiagnosisService: %sの復号に失敗しました: %s", path.name, e)
            return None

    @classmethod
    def _decrypt_answer(cls, chapter: int) -> Optional[str]:
        if chapter in cls._cached_answers:
            return cls._cached_answers[chapter]
        plaintext = cls._decrypt_file(_DATA_DIR / f"chapter{chapter}_answer.enc.json")
        if plaintext is None:
            return None
        answer = plaintext.decode("utf-8")
        cls._cached_answers[chapter] = answer
        return answer

    @classmethod
    def _decrypt_options(cls, chapter: int) -> Optional[List[str]]:
        if chapter in cls._cached_options:
            return cls._cached_options[chapter]
        plaintext = cls._decrypt_file(_DATA_DIR / f"chapter{chapter}_options.enc.json")
        if plaintext is None:
            return None
        options = json.loads(plaintext.decode("utf-8"))
        cls._cached_options[chapter] = options
        return options

    @classmethod
    def get_shuffled_options(cls, chapter: int) -> List[str]:
        """
        指定した章の選択肢を復号し、リクエストごとにシャッフルして返します

        （常に同じ並び順だと、正解の位置を覚えてしまい暗記で突破できてしまうため）
        """
        options = cls._decrypt_options(chapter)
        if options is None:
            return []
        shuffled = list(options)
        random.shuffle(shuffled)
        return shuffled

    @classmethod
    def check_answer(cls, chapter: int, submitted_text: str) -> bool:
        """参加者が選んだ選択肢のテキストが、指定した章の正解と一致するかを判定します"""
        answer = cls._decrypt_answer(chapter)
        if answer is None:
            return False
        return submitted_text.strip() == answer.strip()
