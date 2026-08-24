import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

from app.services.chapter_diagnosis_service import ChapterDiagnosisService

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class NPlusOneQuizService:
    """
    第2章（申請書一覧のN+1クエリ問題）向けの3問構成クイズ
    （パフォーマンス問題の種類 / 発生テーブル / 改善方法）を扱うサービス

    chapter2_answer.enc.json / chapter2_options.enc.json は、ChapterDiagnosisService
    が使う「単一テキスト・単一配列」の形式ではなく、{"q1": [...], "q2": [...], "q3": [...]}
    というJSON構造を暗号化したものとして再利用する（暗号化ファイル形式・復号方法は
    ChapterDiagnosisServiceと共通のため、ファイル復号ヘルパーのみ再利用する）。
    """

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
        """
        3問分の選択肢を復号し、それぞれリクエストごとにシャッフルして返します

        （常に同じ並び順だと、正解の位置を覚えてしまい暗記で突破できてしまうため）
        """
        options = cls._decrypt_options()
        result: Dict[str, List[str]] = {}
        for key in ("q1", "q2", "q3"):
            values = list(options.get(key, []))
            random.shuffle(values)
            result[key] = values
        return result

    @classmethod
    def check_answers(cls, q1: List[str], q2: List[str], q3: List[str]) -> Dict[str, bool]:
        """
        参加者が回答した3問それぞれの選択内容が、指定した問の正解と一致するかを判定します

        Q1・Q3は単一選択、Q2は複数選択だが、いずれも「送信された選択内容の集合」と
        「正解の集合」が完全一致するかどうかで判定する（順序は無視する）。
        """
        answers = cls._decrypt_answers()
        submitted = {"q1": q1, "q2": q2, "q3": q3}

        def _normalize(values: List[str]) -> set:
            return {v.strip() for v in values}

        return {
            key: _normalize(submitted[key]) == _normalize(answers.get(key, []))
            for key in ("q1", "q2", "q3")
        }
