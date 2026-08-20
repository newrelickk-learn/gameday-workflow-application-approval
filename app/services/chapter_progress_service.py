from datetime import datetime, timezone
from typing import List
import hashlib
import logging

from sqlalchemy.orm import Session

from app.models.chapter_progress import ChapterProgress

logger = logging.getLogger(__name__)


class ChapterProgressService:
    """
    GameDay演習の章クリア状態（chapter_progress）を管理するサービス

    company_id + chapterごとに1行のみを保持し、cleared_dateをUPSERTする。
    「進捗は当日のみ有効」の判定は、cleared_date == 今日のUTC日付かどうかで行う。
    """

    @staticmethod
    def _make_id(company_id: str, chapter: int) -> str:
        # company_id + chapterから機械的に導出できる決定的なIDにする
        # （assertion_rulesと同じ考え方。UPSERTのキーとしてそのまま使う）
        raw = f"chapter_progress_{company_id}_{chapter}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def mark_cleared(db: Session, company_id: str, chapter: int) -> ChapterProgress:
        """
        company_id + chapterの組をクリア済みとして記録する（cleared_date = 今日のUTC日付）。
        既に今日クリア済みの場合も同じ日付で上書きするだけで問題ない。
        """
        progress_id = ChapterProgressService._make_id(company_id, chapter)
        today = datetime.now(timezone.utc).date()

        progress = db.query(ChapterProgress).filter(ChapterProgress.id == progress_id).first()
        if progress is None:
            progress = ChapterProgress(
                id=progress_id,
                company_id=company_id,
                chapter=chapter,
                cleared_date=today,
            )
            db.add(progress)
        else:
            progress.cleared_date = today

        db.commit()
        db.refresh(progress)

        logger.info(
            "ChapterProgressService: 章クリアを記録しました - company_id=%s, chapter=%s, cleared_date=%s",
            company_id,
            chapter,
            today,
        )
        return progress

    @staticmethod
    def get_cleared_chapters_today(db: Session, company_id: str) -> List[int]:
        """
        company_idについて、今日のUTC日付でクリア済みの章番号一覧を返す。
        cleared_dateが今日と一致しない行（過去にクリアしたが日付が変わった行）は
        削除せず、単に「未クリア」として扱うためこの一覧には含めない。
        """
        today = datetime.now(timezone.utc).date()
        rows = (
            db.query(ChapterProgress)
            .filter(
                ChapterProgress.company_id == company_id,
                ChapterProgress.cleared_date == today,
            )
            .all()
        )
        return sorted(row.chapter for row in rows)
