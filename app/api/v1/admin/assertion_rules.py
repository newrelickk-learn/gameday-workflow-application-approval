from typing import Any, Dict, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.dependencies import get_db_dependency, get_current_user_dependency
from app.services.user_service import UserService
from app.models.assertion_rule import AssertionRule

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateAssertionRuleRequest(BaseModel):
    """
    assertion_rules恒久対応更新リクエストスキーマ

    単一の共有環境を複数チームが同時に触るため、DBを直接UPDATEするのではなく、
    このAPI経由でチーム（company_id）ごとの行のみを更新できるようにする。
    """
    config: Optional[Dict[str, Any]] = Field(None, description="ルールタイプ毎のパラメータ")
    error_message: Optional[str] = Field(None, alias="errorMessage", description="エラーメッセージ")
    is_active: Optional[bool] = Field(None, alias="isActive", description="有効フラグ")

    class Config:
        populate_by_name = True


class AssertionRuleResponse(BaseModel):
    """assertion_rulesレスポンススキーマ"""
    id: str
    application_type: str = Field(..., alias="applicationType")
    target_field: str = Field(..., alias="targetField")
    rule_type: str = Field(..., alias="ruleType")
    config: Dict[str, Any]
    error_message: Optional[str] = Field(None, alias="errorMessage")
    order: int
    is_active: bool = Field(..., alias="isActive")
    company_id: Optional[str] = Field(None, alias="companyId")

    class Config:
        populate_by_name = True
        from_attributes = True


def _resolve_company_id(current_user: dict) -> Optional[str]:
    """
    認証トークンからCompanyIdを解決します
    （assertion_rulesの更新可否の認可チェックに使用）
    """
    token = current_user.get("_token")
    user_id = current_user.get("user_id") or current_user.get("sub")
    user_info = UserService.get_user_info(user_id, token)
    if not user_info:
        return None
    # PascalCase (CompanyId) と camelCase (companyId) の両方に対応
    company_id = user_info.get("CompanyId") or user_info.get("companyId")
    if company_id is None:
        return None
    return str(company_id)


@router.patch(
    "/admin/assertion-rules/{id}",
    response_model=AssertionRuleResponse,
    status_code=http_status.HTTP_200_OK,
    summary="assertion_rules恒久対応更新",
    description=(
        "assertion_rulesの1行をcompany_idスコープで更新します（恒久対応）。"
        "各チームはcompany_idごとに個別のルール行（id: "
        "assertion_rule_{application_type}_{target_field}_{company_id} 等の命名）を持つ。"
        "認証トークンから取得したcompany_idと、更新対象行のcompany_idが一致する場合のみ"
        "更新を許可します（他チームの行は更新できません）。"
    ),
    responses={
        401: {"description": "認証が必要です／CompanyIdが取得できません"},
        403: {"description": "他チームの行のため更新権限がありません"},
        404: {"description": "指定されたIDのルールが見つかりません"},
    },
)
async def update_assertion_rule(
    id: str,
    request: UpdateAssertionRuleRequest,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> AssertionRuleResponse:
    """assertion_rulesの1行をcompany_idスコープで更新します"""
    rule = db.query(AssertionRule).filter(AssertionRule.id == id).first()
    if not rule:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": "ASSERTION_RULE_NOT_FOUND", "message": "指定されたIDのルールが見つかりません"},
        )

    token_company_id = _resolve_company_id(current_user)
    if token_company_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "ユーザーのCompanyIdが取得できませんでした"},
        )

    # 認可チェック: トークンのcompany_idと対象行のcompany_idが一致する場合のみ更新可。
    # company_id is None の分岐は防御的に残す（現行のシードは各チームがcompany_idごとの
    # 専用行を最初から持つ運用のため、通常はこの分岐に到達しない想定）。
    if rule.company_id is None or rule.company_id != token_company_id:
        logger.warning(
            "AssertionRulesAdmin: 権限のないcompany_idからの更新要求を拒否しました - "
            "rule_id=%s, rule_company_id=%s, token_company_id=%s",
            id, rule.company_id, token_company_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "このルールを更新する権限がありません"},
        )

    if request.config is not None:
        rule.config = request.config
    if request.error_message is not None:
        rule.error_message = request.error_message
    if request.is_active is not None:
        rule.is_active = request.is_active

    db.commit()
    db.refresh(rule)

    logger.info("AssertionRulesAdmin: ルールを更新しました - rule_id=%s, company_id=%s", id, token_company_id)

    return AssertionRuleResponse.model_validate(rule)
