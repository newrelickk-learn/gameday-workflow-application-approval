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

    _cached_answers: Dict[int, str] = {}
    _cached_options: Dict[int, List[str]] = {}
    _cached_list_answers: Dict[int, List[str]] = {}

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
        options = cls._decrypt_options(chapter)
        if options is None:
            return []
        shuffled = list(options)
        random.shuffle(shuffled)
        return shuffled

    @classmethod
    def check_answer(cls, chapter: int, submitted_text: str) -> bool:
        answer = cls._decrypt_answer(chapter)
        if answer is None:
            return False
        return submitted_text.strip() == answer.strip()

    @classmethod
    def _decrypt_list_answer(cls, name: str) -> Optional[List[str]]:
        cache_key = name
        if cache_key in cls._cached_list_answers:
            return cls._cached_list_answers[cache_key]
        plaintext = cls._decrypt_file(_DATA_DIR / f"{name}.enc.json")
        if plaintext is None:
            return None
        answer = json.loads(plaintext.decode("utf-8"))
        cls._cached_list_answers[cache_key] = answer
        return answer

    @classmethod
    def check_ordered_list_answer(cls, name: str, submitted: List[str]) -> bool:
        answer = cls._decrypt_list_answer(name)
        if answer is None:
            return False
        return list(submitted) == list(answer)
