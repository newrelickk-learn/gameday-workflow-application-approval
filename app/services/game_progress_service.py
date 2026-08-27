from typing import Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationType
from app.models.game_progress import GameProgress

logger = logging.getLogger(__name__)


class GameProgressService:

    EXPENSE_FIXED_ADVANCE_DAYS = 3

    @staticmethod
    def get_active_progress(db: Session, company_id: str) -> Optional[GameProgress]:
        return (
            db.query(GameProgress)
            .filter(
                GameProgress.company_id == str(company_id),
                GameProgress.is_active == True,  
            )
            .order_by(GameProgress.created_at.desc())
            .first()
        )

    @staticmethod
    def apply_approved_application(
        db: Session,
        application: Application,
        company_id: Optional[str],
    ) -> Optional[GameProgress]:
        if not company_id:
            logger.warning(
                "GameProgressService: company_idが取得できないためgame_progressを更新できません。"
                "application_id=%s",
                application.id,
            )
            return None

        progress = GameProgressService.get_active_progress(db, company_id)
        if not progress:
            logger.warning(
                "GameProgressService: company_id=%sのgame_progressが見つかりません。application_id=%s",
                company_id,
                application.id,
            )
            return None

        app_type = application.type

        if app_type == ApplicationType.BUSINESS_TRIP.value:
            days = application.days or 0
            progress.virtual_date_offset_days = progress.virtual_date_offset_days + days
        elif app_type == ApplicationType.EXPENSE.value:
            progress.virtual_date_offset_days = (
                progress.virtual_date_offset_days + GameProgressService.EXPENSE_FIXED_ADVANCE_DAYS
            )
        elif app_type == ApplicationType.PROMOTION.value:
            progress.virtual_date_offset_days = 0
        else:
            return None

        progress.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(progress)

        logger.info(
            "GameProgressService: game_progressを更新しました - company_id=%s, "
            "application_type=%s, virtual_date_offset_days=%s",
            company_id,
            app_type,
            progress.virtual_date_offset_days,
        )
        return progress

    @staticmethod
    def set_offset(
        db: Session,
        company_id: str,
        virtual_date_offset_days: int,
    ) -> Optional[GameProgress]:
        progress = GameProgressService.get_active_progress(db, company_id)
        if not progress:
            logger.warning(
                "GameProgressService: company_id=%sのgame_progressが見つかりません（set_offset）",
                company_id,
            )
            return None

        progress.virtual_date_offset_days = virtual_date_offset_days
        progress.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(progress)

        logger.info(
            "GameProgressService: virtual_date_offset_daysを直接設定しました - "
            "company_id=%s, virtual_date_offset_days=%s",
            company_id,
            virtual_date_offset_days,
        )
        return progress
