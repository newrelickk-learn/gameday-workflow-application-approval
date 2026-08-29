import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

from app.services.chapter_diagnosis_service import ChapterDiagnosisService

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class RageClickQuizService:

    _cached_answers: Optional[Dict[str, str]] = None
    _cached_options: Optional[Dict[str, List[str]]] = None

    @classmethod
    def _decrypt_answers(cls) -> Dict[str, str]:
        if cls._cached_answers is not None:
            return cls._cached_answers
        plaintext = ChapterDiagnosisService._decrypt_file(_DATA_DIR / "chapter4_ragequiz_answer.enc.json")
        if plaintext is None:
            return {}
        answers = json.loads(plaintext.decode("utf-8"))
        cls._cached_answers = answers
        return answers

    @classmethod
    def _decrypt_options(cls) -> Dict[str, List[str]]:
        if cls._cached_options is not None:
            return cls._cached_options
        plaintext = ChapterDiagnosisService._decrypt_file(_DATA_DIR / "chapter4_ragequiz_options.enc.json")
        if plaintext is None:
            return {}
        options = json.loads(plaintext.decode("utf-8"))
        cls._cached_options = options
        return options

    @classmethod
    def get_shuffled_options(cls) -> Dict[str, List[str]]:
        options = cls._decrypt_options()
        result: Dict[str, List[str]] = {}
        for key in ("q1", "q2", "q3"):
            values = list(options.get(key, []))
            random.shuffle(values)
            result[key] = values
        return result

    @classmethod
    def check_answers(cls, q1: str, q2: str, q3: str) -> Dict[str, bool]:
        answers = cls._decrypt_answers()
        submitted = {"q1": q1, "q2": q2, "q3": q3}
        return {
            key: submitted[key].strip() == answers.get(key, "").strip()
            for key in ("q1", "q2", "q3")
        }
