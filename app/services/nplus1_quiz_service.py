import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

from app.services.chapter_diagnosis_service import ChapterDiagnosisService

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class NPlusOneQuizService:

    _cached_answers: Optional[Dict[str, List[str]]] = None
    _cached_options: Optional[Dict[str, List[str]]] = None

    @classmethod
    def _decrypt_answers(cls) -> Dict[str, List[str]]:
        if cls._cached_answers is not None:
            return cls._cached_answers
        plaintext = ChapterDiagnosisService._decrypt_file(_DATA_DIR / "chapter2_answer.enc.json")
        if plaintext is None:
            return {}
        answers = json.loads(plaintext.decode("utf-8"))
        cls._cached_answers = answers
        return answers

    @classmethod
    def _decrypt_options(cls) -> Dict[str, List[str]]:
        if cls._cached_options is not None:
            return cls._cached_options
        plaintext = ChapterDiagnosisService._decrypt_file(_DATA_DIR / "chapter2_options.enc.json")
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
    def check_answers(cls, q1: List[str], q2: List[str], q3: List[str]) -> Dict[str, bool]:
        answers = cls._decrypt_answers()
        submitted = {"q1": q1, "q2": q2, "q3": q3}

        def _normalize(values: List[str]) -> set:
            return {v.strip() for v in values}

        return {
            key: _normalize(submitted[key]) == _normalize(answers.get(key, []))
            for key in ("q1", "q2", "q3")
        }
