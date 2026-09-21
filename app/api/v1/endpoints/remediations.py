"""ランブック記載の暫定対応を、アクセスした人の会社にだけ適用するAPI。

New RelicのAIエージェントがアラートを調査すると、ナレッジに取り込んだランブック
(gameday-workflow-docs/troubleshoot/approved-list-slow-troubleshoot.md)から暫定対応の
URLが提示される。フロントのランブックページがこのAPIを呼ぶ。

原因の切り分けが終わっていない状態で適用されると、調査対象の事象そのものが消えてしまうため、
原因診断(第2章)をクリアしていることを条件にしている。
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
import newrelic.agent

from app.api.dependencies import get_db_dependency, get_current_user_dependency
from app.schemas.application import ErrorResponse
from app.services.game_master_client import GameMasterClient
from app.services.remediation_service import RemediationService, FEATURE_APPROVED_LIST_SLOW
from app.services.user_service import UserService
from app.services import hidden_quest_token

logger = logging.getLogger(__name__)

router = APIRouter()

# 承認済み一覧の遅延について、原因診断が完了していることを示す章。
# これをクリアする前に暫定対応を当ててしまうと、調査対象の事象自体が消えてしまう。
INVESTIGATION_CHAPTER = 2


def _resolve_company_id(user_id: Optional[str], token: Optional[str]) -> Optional[int]:
    user_info = UserService.get_user_info(user_id, token)
    if not user_info:
        return None

    company_id = user_info.get("CompanyId") or user_info.get("companyId")
    if company_id is None:
        return None

    try:
        return int(company_id)
    except (ValueError, TypeError):
        return None


@router.get(
    "/remediations/approved-list-slow",
    status_code=http_status.HTTP_200_OK,
    summary="承認済み一覧の暫定対応の適用状況",
    description="ログイン中のユーザーが所属する会社に、暫定対応が適用済みかどうかを返します",
    responses={401: {"model": ErrorResponse, "description": "認証が必要です"}},
)
async def get_approved_list_remediation(
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> dict:
    newrelic.agent.set_transaction_name('/v0.1/remediations/approved-list-slow')

    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    company_id = _resolve_company_id(user_id, token)
    if company_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "ユーザー情報を取得できませんでした"},
        )

    applied = RemediationService.is_applied(db, company_id, FEATURE_APPROVED_LIST_SLOW)
    newrelic.agent.add_custom_attribute('company_id', company_id)
    newrelic.agent.add_custom_attribute('remediation_applied', applied)

    return {"applied": applied, "companyId": company_id}


@router.post(
    "/remediations/approved-list-slow",
    status_code=http_status.HTTP_200_OK,
    summary="承認済み一覧の暫定対応を適用",
    description="ログイン中のユーザーが所属する会社にのみ、一覧取得の読み込み方法の切り替えを適用します",
    responses={401: {"model": ErrorResponse, "description": "認証が必要です"}},
)
async def apply_approved_list_remediation(
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> dict:
    newrelic.agent.set_transaction_name('/v0.1/remediations/approved-list-slow')

    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    company_id = _resolve_company_id(user_id, token)
    if company_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "ユーザー情報を取得できませんでした"},
        )

    newrelic.agent.add_custom_attribute('company_id', company_id)

    if RemediationService.is_applied(db, company_id, FEATURE_APPROVED_LIST_SLOW):
        newrelic.agent.add_custom_attribute('remediation_result', 'already_applied')
        return {"applied": True, "alreadyApplied": True, "reason": None, "hiddenQuestTokens": None}

    # 原因の切り分けが終わっていない環境には適用しない。
    cleared_chapters = GameMasterClient.get_cleared_chapters_today(token)
    if INVESTIGATION_CHAPTER not in cleared_chapters:
        newrelic.agent.add_custom_attribute('remediation_result', 'investigation_incomplete')
        logger.info(
            f"RemediationService: 原因の切り分けが未完了のため適用しません。company_id={company_id}"
        )
        return {
            "applied": False,
            "alreadyApplied": False,
            "reason": "investigation_incomplete",
            "hiddenQuestTokens": None,
        }

    RemediationService.apply(db, company_id, FEATURE_APPROVED_LIST_SLOW)
    newrelic.agent.add_custom_attribute('remediation_result', 'applied')

    quest_token = hidden_quest_token.issue(
        str(company_id), hidden_quest_token.HIDDEN_QUEST_APPROVED_LIST_REMEDIATION
    )

    return {
        "applied": True,
        "alreadyApplied": False,
        "reason": None,
        "hiddenQuestTokens": [quest_token] if quest_token else None,
    }
