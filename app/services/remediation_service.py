"""会社単位の暫定対応(是正)の適用と判定。

New RelicのAIエージェントがアラートを調査する際、ナレッジに取り込んだランブックから
暫定対応のURLが提示される。そのURLにアクセスした人の会社にだけ是正が適用される、という
GameDayの仕掛けのためのサービス。

是正は当日スコープ(applied_date)で、日次のリセットで消える。
"""

from datetime import date, datetime, timezone
from typing import Optional
import logging

from sqlalchemy.orm import Session

from app.models.application import CompanyRemediation

logger = logging.getLogger(__name__)

# 承認済み一覧の表示遅延(一覧取得で関連データを行ごとに引いている)に対する暫定対応。
FEATURE_APPROVED_LIST_SLOW = "approved-list-slow"


def _today() -> date:
    return datetime.now(timezone.utc).date()


class RemediationService:

    @staticmethod
    def is_applied(db: Session, company_id: Optional[int], feature: str) -> bool:
        """その会社に当日分の是正が適用済みかどうか。"""
        if company_id is None:
            return False

        row = (
            db.query(CompanyRemediation)
            .filter(
                CompanyRemediation.company_id == company_id,
                CompanyRemediation.feature == feature,
            )
            .first()
        )

        return row is not None and row.applied_date == _today()

    @staticmethod
    def apply(db: Session, company_id: int, feature: str) -> None:
        """是正を適用する。すでに適用済みなら当日分として上書きするだけ。"""
        row = (
            db.query(CompanyRemediation)
            .filter(
                CompanyRemediation.company_id == company_id,
                CompanyRemediation.feature == feature,
            )
            .first()
        )

        if row is None:
            row = CompanyRemediation(
                company_id=company_id,
                feature=feature,
                applied_date=_today(),
            )
            db.add(row)
        else:
            row.applied_date = _today()

        db.commit()

        logger.info(
            f"RemediationService: 暫定対応を適用しました。company_id={company_id}, feature={feature}"
        )
