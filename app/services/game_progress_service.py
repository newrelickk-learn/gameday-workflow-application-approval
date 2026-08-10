from typing import Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationType
from app.models.game_progress import GameProgress

logger = logging.getLogger(__name__)


class GameProgressService:
    """
    GameDay演習の仮想時間進行（game_progress.virtual_date_offset_days）を管理するサービス

    バックエンドの実際のバリデーションには一切使わず、フロントエンドの
    「仮想今日」表示（getVirtualToday()）のためだけに更新される。
    """

    # 経費申請の承認完了ごとに進む固定日数（事務処理にかかる想定日数）
    EXPENSE_FIXED_ADVANCE_DAYS = 3

    @staticmethod
    def get_active_progress(db: Session, company_id: str) -> Optional[GameProgress]:
        """
        company_idに対応する現在進行中（is_active=true）のgame_progress行を取得します

        Args:
            db: データベースセッション
            company_id: 会社ID（チームの分離単位）

        Returns:
            現在進行中のGameProgress行、存在しない場合はNone
        """
        return (
            db.query(GameProgress)
            .filter(
                GameProgress.company_id == str(company_id),
                GameProgress.is_active == True,  # noqa: E712
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
        """
        申請が approved になった際に、申請タイプ別のルールで
        virtual_date_offset_days を更新します。

        - business-trip: 申請のdays（実際の出張日数）分だけ進める
        - expense: 固定で+3日進める（承認完了ごとに毎回積み上がる）
        - promotion: 無条件に0へリセット（ゲームのフィニッシュ）
        - その他（vacation等）: 進行ルールの対象外のため何もしない

        Args:
            db: データベースセッション
            application: approvedになった申請
            company_id: 申請者の会社ID

        Returns:
            更新後のGameProgress行、更新対象がない場合はNone
        """
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
            # 1年間の細かい進行のズレを気にせず、最後に必ず「今日」へジャンプする特別処理
            progress.virtual_date_offset_days = 0
        else:
            # vacation等、game_progressの進行ルール対象外の申請タイプは何もしない
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
