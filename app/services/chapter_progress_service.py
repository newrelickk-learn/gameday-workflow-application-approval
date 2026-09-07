from datetime import datetime, timezone
from typing import Dict, List
import hashlib
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chapter_progress import ChapterProgress

logger = logging.getLogger(__name__)


class ChapterProgressService:

    @staticmethod
    def _make_id(company_id: str, chapter: int) -> str:
        raw = f"chapter_progress_{company_id}_{chapter}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def mark_cleared(db: Session, company_id: str, chapter: int) -> ChapterProgress:
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

    @staticmethod
    def get_cleared_counts_today(db: Session) -> Dict[str, int]:
        today = datetime.now(timezone.utc).date()
        rows = (
            db.query(ChapterProgress.company_id, func.count(ChapterProgress.chapter))
            .filter(ChapterProgress.cleared_date == today)
            .group_by(ChapterProgress.company_id)
            .all()
        )
        return {company_id: count for company_id, count in rows}
