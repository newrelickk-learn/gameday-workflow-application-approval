from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session
import newrelic.agent

from app.api.dependencies import get_db_dependency, get_current_user_dependency
from app.core.i18n import t
from app.services.application_service import ApplicationService
from app.services.workflow_service import WorkflowService
from app.services.user_service import UserService
from app.services import game_master_tokens
from app.services.validation_service import ValidationError
from app.models.application import ApplicationStatus
from pydantic import BaseModel, Field

router = APIRouter()

logger = logging.getLogger(__name__)


class ApproverNotFoundException(HTTPException):
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": "APPROVER_NOT_FOUND", "message": message, "field": field},
        )


def _issue_game_progress_token(application, token: Optional[str]) -> Optional[str]:
    """承認完了した申請で仮想時間を進めるためのトークンを発行する。

    ここからgame-masterを呼ぶと承認のトレースにgame-masterが混ざるため、トークンを
    レスポンスに載せてfrontendからgame-masterへ届けてもらう。
    """
    try:
        applicant_info = UserService.get_user_info(application.applicant_id, token)
        company_id = None
        if applicant_info:
            company_id = applicant_info.get("CompanyId") or applicant_info.get("companyId")
        if company_id is None:
            return None
        return game_master_tokens.issue_approved_application(
            str(company_id), application.type, application.days
        )
    except Exception as e:
        logger.error(
            f"ApprovalService: game_progress更新用トークンの発行中にエラーが発生しました - "
            f"application_id={getattr(application, 'id', None)}, error={e}"
        )
        return None


class UpdateApprovalRequest(BaseModel):
    approval_id: str = Field(..., alias="approvalId", description="承認ID")
    application_id: str = Field(..., alias="applicationId", description="申請ID")
    approver_id: str = Field(..., alias="approverId", description="承認者ID")
    status: str = Field(..., description="承認ステータス（approved/rejected）")
    comment: Optional[str] = Field(None, description="コメント")
    
    class Config:
        populate_by_name = True


class UpdateApprovalResponse(BaseModel):
    success: bool = Field(..., description="更新成功フラグ")
    message: str = Field(..., description="レスポンスメッセージ")
    application_status: Optional[str] = Field(None, alias="applicationStatus", description="更新後の申請ステータス")
    game_progress_token: Optional[str] = Field(
        None,
        alias="gameProgressToken",
        description="承認完了で仮想時間を進めるためのトークン。frontendがgame-masterへ届ける",
    )

    class Config:
        populate_by_name = True


@router.post(
    "/approvals/update",
    response_model=UpdateApprovalResponse,
    status_code=http_status.HTTP_200_OK,
    summary="承認更新",
    description="承認を更新し、申請ステータスを更新します",
)
async def update_approval(
    request: UpdateApprovalRequest,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> UpdateApprovalResponse:
    try:
        newrelic.agent.add_custom_attribute('approval_id', request.approval_id)
        newrelic.agent.add_custom_attribute('application_id', request.application_id)
        newrelic.agent.add_custom_attribute('approver_id', request.approver_id)
        newrelic.agent.add_custom_attribute('approval_action', request.status)

        token = current_user.get("_token")
        
        application = ApplicationService.get_application(db, request.application_id)
        if not application:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Application not found",
                    "message": "指定された申請IDの申請が見つかりません",
                },
            )
        
        workflow_result = WorkflowService.approve_workflow(
            approval_id=request.approval_id,
            application_id=request.application_id,
            approver_id=request.approver_id,
            status=request.status,
            token=token
        )
        
        if workflow_result:
            logger.info(f"ApprovalService: ワークフローサービスで承認を記録しました - "
                       f"application_id={request.application_id}, "
                       f"current_step={workflow_result.get('currentStep')}, "
                       f"status={workflow_result.get('status')}")
        else:
            logger.warning(f"ApprovalService: ワークフローサービスへの承認記録に失敗しましたが、処理を続行します - "
                          f"application_id={request.application_id}")
        
        if request.status == "approved":
            if application.current_step is not None and application.total_steps is not None:
                current_step = application.current_step
                total_steps = application.total_steps
                
                logger.info(f"ApprovalService: 承認処理開始 - application_id={request.application_id}, "
                           f"current_step={current_step}, total_steps={total_steps}")
                
                next_step = current_step + 1
                
                if next_step > total_steps:
                    ApplicationService.update_application_status(
                        db, request.application_id, ApplicationStatus.APPROVED
                    )
                    application.current_step = None
                    application.next_approver_id = None
                    application.next_approver_name = None
                    application.next_approver_department = None
                    db.commit()
                    db.refresh(application)

                    game_progress_token = _issue_game_progress_token(application, token)

                    logger.info(f"ApprovalService: 申請を承認しました（全ステップ完了） - application_id={request.application_id}")
                    newrelic.agent.add_custom_attribute('application_status', 'approved')
                    return UpdateApprovalResponse(
                        success=True,
                        message=t("approval_completed"),
                        application_status="approved",
                        game_progress_token=game_progress_token,
                    )
                else:
                    applicant_info = UserService.get_user_info(application.applicant_id, token)
                    
                    if not applicant_info:
                        raise HTTPException(
                            status_code=http_status.HTTP_404_NOT_FOUND,
                            detail={"error": "USER_NOT_FOUND", "message": f"申請者情報が取得できません: applicant_id={application.applicant_id}"}
                        )
                    
                    company_id = applicant_info.get("CompanyId") or applicant_info.get("companyId")
                    if company_id:
                        try:
                            company_id = int(company_id)
                        except (ValueError, TypeError):
                            raise HTTPException(
                                status_code=http_status.HTTP_400_BAD_REQUEST,
                                detail={"error": "INVALID_COMPANY_ID", "message": f"CompanyIdが不正です: {company_id}"}
                            )
                    
                    if not company_id:
                        raise HTTPException(
                            status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": "COMPANY_ID_NOT_FOUND", "message": f"申請者のCompanyIdが取得できません: applicant_id={application.applicant_id}"}
                        )

                    newrelic.agent.add_custom_attribute('company_id', company_id)

                    try:
                        next_approver_id, next_approver_name, next_approver_department, _, _ = \
                            ApplicationService._determine_approver(
                                application.type, company_id, token, next_step,
                                applicant_id=application.applicant_id,
                                amount=application.amount,
                            )
                    except ValidationError as e:
                        if e.error_code == "APPROVER_NOT_FOUND":
                            newrelic.agent.add_custom_attribute('validation_error', e.error_code)
                            raise ApproverNotFoundException(message=e.message, field=e.field)
                        raise
                    
                    if next_approver_id is None:
                        ApplicationService.update_application_status(
                            db, request.application_id, ApplicationStatus.APPROVED
                        )
                        application.current_step = None
                        application.next_approver_id = None
                        application.next_approver_name = None
                        application.next_approver_department = None
                        db.commit()
                        db.refresh(application)

                        game_progress_token = _issue_game_progress_token(application, token)

                        logger.info(f"ApprovalService: 申請を承認しました（全ステップ完了） - application_id={request.application_id}")
                        newrelic.agent.add_custom_attribute('application_status', 'approved')
                        return UpdateApprovalResponse(
                            success=True,
                            message=t("approval_completed"),
                            application_status="approved",
                            game_progress_token=game_progress_token,
                        )

                    application.current_step = next_step
                    application.next_approver_id = next_approver_id
                    application.next_approver_name = next_approver_name
                    application.next_approver_department = next_approver_department
                    db.commit()
                    db.refresh(application)
                    
                    logger.info(f"ApprovalService: 承認完了、次のステップへ - application_id={request.application_id}, "
                               f"current_step={current_step} -> next_step={next_step}, "
                               f"next_approver_id={next_approver_id}, next_approver_name={next_approver_name}")
                    if next_step:
                        newrelic.agent.add_custom_attribute('next_step', next_step)
                    if next_approver_id:
                        newrelic.agent.add_custom_attribute('next_approver_id', next_approver_id)
                    newrelic.agent.add_custom_attribute('application_status', 'pending')
                    return UpdateApprovalResponse(
                        success=True,
                        message=f"承認が完了しました。ステップ{next_step}/{total_steps}の承認者に送られました",
                        application_status="pending"
                    )
            else:
                ApplicationService.update_application_status(
                    db, request.application_id, ApplicationStatus.APPROVED
                )

                game_progress_token = _issue_game_progress_token(application, token)

                logger.info(f"ApprovalService: 申請を承認しました（ステップ情報なし） - application_id={request.application_id}")
                newrelic.agent.add_custom_attribute('application_status', 'approved')
                return UpdateApprovalResponse(
                    success=True,
                    message=t("approval_completed"),
                    application_status="approved",
                    game_progress_token=game_progress_token,
                )
        elif request.status == "rejected":
            ApplicationService.update_application_status(
                db, request.application_id, ApplicationStatus.REJECTED
            )
            logger.info(f"ApprovalService: 申請を却下しました - application_id={request.application_id}")
            newrelic.agent.add_custom_attribute('application_status', 'rejected')
            return UpdateApprovalResponse(
                success=True,
                message=t("application_rejected"),
                application_status="rejected"
            )
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_STATUS",
                    "message": f"不正な承認ステータスです: {request.status}",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ApprovalService: 承認更新エラー - {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )

