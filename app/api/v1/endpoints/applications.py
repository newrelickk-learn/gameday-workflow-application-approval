from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy.orm import Session
import newrelic.agent

from app.api.dependencies import get_db_dependency, get_current_user_dependency

logger = logging.getLogger(__name__)
from app.schemas.application import Application, CreateApplicationRequest, ErrorResponse
from app.services.application_service import ApplicationService
from app.services.validation_service import ValidationService, ValidationError
from app.services.user_service import UserService
from app.models.application import ApplicationStatus

router = APIRouter()


@router.get(
    "/applications",
    response_model=List[Application],
    status_code=http_status.HTTP_200_OK,
    summary="申請一覧取得",
    description="すべての申請を取得します",
    responses={
        401: {"model": ErrorResponse, "description": "認証が必要です"},
        500: {"model": ErrorResponse, "description": "サーバーエラー"},
    },
)
async def get_applications(
    status: Optional[ApplicationStatus] = Query(None, description="申請ステータスでフィルタリング"),
    applicant_id: Optional[str] = Query(None, description="申請者IDでフィルタリング", alias="applicantId"),
    application_number: Optional[str] = Query(None, description="申請書番号でフィルタリング", alias="applicationNumber"),
    next_approver_id: Optional[str] = Query(None, description="次の承認者IDでフィルタリング", alias="nextApproverId"),
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> List[Application]:
    """申請一覧を取得します"""
    newrelic.agent.set_transaction_name('/v0.1/applications')
    
    try:
        # トークンとユーザーIDを取得
        token = current_user.get("_token")
        user_id = current_user.get("user_id") or current_user.get("sub")
        
        # カスタム属性: ユーザー情報
        newrelic.agent.add_custom_attribute('user_id', user_id)
        if status:
            status_value = status.value if hasattr(status, 'value') else str(status)
            newrelic.agent.add_custom_attribute('filter_status', status_value)
        if applicant_id:
            newrelic.agent.add_custom_attribute('filter_applicant_id', applicant_id)
        if application_number:
            newrelic.agent.add_custom_attribute('filter_application_number', application_number)
        if next_approver_id:
            newrelic.agent.add_custom_attribute('filter_next_approver_id', next_approver_id)

        # ログインユーザーの会社IDを取得
        current_user_info = UserService.get_user_info(user_id, token)
        if not current_user_info:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail={"error": "UNAUTHORIZED", "message": "ユーザー情報を取得できませんでした"},
            )
        # PascalCase (CompanyId) と camelCase (companyId) の両方に対応
        current_company_id = current_user_info.get("CompanyId") or current_user_info.get("companyId")
        # 型を統一（intに変換）
        if current_company_id:
            try:
                current_company_id = int(current_company_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid current_company_id: {current_company_id}")
                current_company_id = None
        
        # カスタム属性: 会社ID、ユーザーロール
        if current_company_id:
            newrelic.agent.add_custom_attribute('company_id', current_company_id)
        user_role = current_user_info.get("role")
        if user_role:
            newrelic.agent.add_custom_attribute('user_role', user_role)
        
        # applicantId未指定（承認者向け「申請書一覧」等の全件取得）の場合は、
        # company_idでDBレベルに絞り込む（以前はcompany_idフィルタが無く全社分を
        # LIMIT 1000で一括取得してからPythonループで絞り込んでいたため、データ量が
        # 増えるとN+1ループの対象行数が肥大化しPodのliveness probeタイムアウトを
        # 引き起こした）。件数上限は設けない（ORDER BY created_at DESCと合わせて、
        # 以前あった「101件目以降が一覧から漏れる」問題を解消する）。
        applications = ApplicationService.get_applications(
            db=db,
            status=status,
            applicant_id=applicant_id,
            application_number=application_number,
            next_approver_id=next_approver_id,
            company_id=current_company_id if not applicant_id and not next_approver_id else None,
        )
        
        # カスタム属性: 取得した申請数
        newrelic.agent.add_custom_attribute('applications_count', len(applications))
        
        # 各申請の申請者名を取得し、同じ会社の申請のみフィルタリング
        # 申請者IDをまとめて重複除去し、UserServiceへは1回のバッチ呼び出しのみ行う
        # （以前は申請1件ごとにget_user_infoを呼んでおり、申請件数分のN+1が発生していた）
        unique_applicant_ids = {app.applicant_id for app in applications if app.applicant_id}
        applicant_info_map = UserService.get_users_info(unique_applicant_ids, token)
        newrelic.agent.add_custom_attribute('unique_applicant_count', len(unique_applicant_ids))

        result = []
        for app in applications:
            app_dict = Application.model_validate(app).model_dump()
            # 各申請の最新コメントを取得（comments relationshipへの初回アクセスで
            # 申請ごとに個別SELECTが発行される）
            if app.comments:
                latest_comment = max(app.comments, key=lambda c: c.created_at)
                app_dict["latestComment"] = latest_comment.body
            # 経費精算のレシート画像一覧を取得（receipt_images relationshipへの初回アクセス）
            if app.receipt_images:
                app_dict["receiptImageUrls"] = [img.image_url for img in app.receipt_images]

            applicant_info = applicant_info_map.get(str(app.applicant_id)) if app.applicant_id else None

            # 申請者名が設定されていない場合、UserServiceから取得
            if not app_dict.get("applicantName") and app.applicant_id:
                if applicant_info:
                    # 同じ会社の申請のみ追加
                    applicant_company_id = applicant_info.get("CompanyId") or applicant_info.get("companyId")
                    if applicant_company_id == current_company_id:
                        app_dict["applicantName"] = applicant_info.get("name")
                        app_dict["applicantDepartment"] = applicant_info.get("department")
                        result.append(Application(**app_dict))
                    else:
                        logger.info(
                            f"[CompanyFilter] Skipping application {app.id} from different company: "
                            f"applicant_company={applicant_company_id}, "
                            f"current_company={current_company_id}"
                        )
            else:
                # 申請者名が既に設定されている場合も会社チェックが必要
                applicant_company_id = applicant_info.get("CompanyId") or applicant_info.get("companyId") if applicant_info else None
                if applicant_info and applicant_company_id == current_company_id:
                    result.append(Application(**app_dict))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_applications: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


# 注意: パスパラメータを使う "/applications/{id}" より前に定義する必要がある
# （FastAPIはルートを定義順に評価するため、後に定義すると "count" がidとして
# マッチしてしまう）。
@router.get(
    "/applications/count",
    status_code=http_status.HTTP_200_OK,
    summary="申請件数取得",
    description="申請の件数のみを取得します（申請者名・コメント等の付随情報は取得しないため、"
                "一覧取得と違いN+1が発生せず高速）",
    responses={
        401: {"model": ErrorResponse, "description": "認証が必要です"},
        500: {"model": ErrorResponse, "description": "サーバーエラー"},
    },
)
async def get_applications_count(
    status: Optional[ApplicationStatus] = Query(None, description="申請ステータスでフィルタリング"),
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> dict:
    """申請件数のみを取得します（ダッシュボードのカード表示等、件数だけが必要な場面用）"""
    newrelic.agent.set_transaction_name('/v0.1/applications/count')
    try:
        token = current_user.get("_token")
        user_id = current_user.get("user_id") or current_user.get("sub")
        newrelic.agent.add_custom_attribute('user_id', user_id)
        if status:
            newrelic.agent.add_custom_attribute(
                'filter_status', status.value if hasattr(status, 'value') else str(status)
            )

        current_user_info = UserService.get_user_info(user_id, token)
        if not current_user_info:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail={"error": "UNAUTHORIZED", "message": "ユーザー情報を取得できませんでした"},
            )
        current_company_id = current_user_info.get("CompanyId") or current_user_info.get("companyId")
        if current_company_id:
            try:
                current_company_id = int(current_company_id)
            except (ValueError, TypeError):
                current_company_id = None

        count = ApplicationService.count_applications(
            db=db, status=status, company_id=current_company_id
        )
        newrelic.agent.add_custom_attribute('applications_count', count)
        return {"count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_applications_count: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.post(
    "/applications",
    response_model=Application,
    status_code=http_status.HTTP_201_CREATED,
    summary="申請作成",
    description="新しい申請を作成します",
    responses={
        400: {"model": ErrorResponse, "description": "リクエストが不正です"},
        401: {"model": ErrorResponse, "description": "認証が必要です"},
        500: {"model": ErrorResponse, "description": "サーバーエラー"},
    },
)
async def create_application(
    application_data: CreateApplicationRequest,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> Application:
    """申請を作成します"""
    newrelic.agent.set_transaction_name('/v0.1/create_application')
    
    try:
        # ユーザーIDを取得
        user_id = current_user.get("user_id") or current_user.get("sub")
        logger.info(
            "create_application: type=%s applicant_id=%s current_user_id=%s",
            getattr(application_data, "type", None),
            getattr(application_data, "applicant_id", None),
            user_id,
        )
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "UNAUTHORIZED",
                    "message": "ユーザーIDが取得できませんでした",
                },
            )
        
        # カスタム属性: 申請タイプ、申請者ID
        newrelic.agent.add_custom_attribute('application_type', application_data.type)
        newrelic.agent.add_custom_attribute('applicant_id', application_data.applicant_id)
        newrelic.agent.add_custom_attribute('user_id', user_id)
        
        # トークンを取得（外部サービス呼び出し時に使用）
        token = current_user.get("_token")
        
        # バリデーション実行
        ValidationService.validate_application(application_data, user_id, token, db)
        
        application = ApplicationService.create_application(
            db=db,
            application_data=application_data,
            token=token,
        )
        
        # カスタム属性: 作成された申請のステータスとID
        newrelic.agent.add_custom_attribute('application_id', application.id)
        status_value = application.status.value if hasattr(application.status, 'value') else str(application.status)
        newrelic.agent.add_custom_attribute('application_status', status_value)
        if application_data.amount:
            newrelic.agent.add_custom_attribute('application_amount', application_data.amount)
        if application_data.days:
            newrelic.agent.add_custom_attribute('application_days', application_data.days)
        newrelic.agent.add_custom_attribute('application_current_step', application.current_step)
        newrelic.agent.add_custom_attribute('application_total_steps', application.total_steps)
        newrelic.agent.add_custom_attribute('application_next_approver_id', application.next_approver_id)

        # Pydanticモデルを返す（FastAPIが自動的にaliasを使用してキャメルケースで返す）
        return Application.model_validate(application)
    except ValidationError as e:
        newrelic.agent.add_custom_attribute('validation_error', e.error_code)
        newrelic.agent.add_custom_attribute('validation_message', e.message)
        # 国内出張バグ調査用のカスタム属性（開始日・終了日・日数差分）
        newrelic.agent.add_custom_attribute('req_start_date', str(application_data.start_date))
        newrelic.agent.add_custom_attribute('req_end_date', str(application_data.end_date))
        newrelic.agent.add_custom_attribute(
            'req_date_diff_days',
            (application_data.end_date - application_data.start_date).days
            if application_data.start_date and application_data.end_date else None
        )
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": e.message,
                "field": e.field,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )


@router.get(
    "/applications/{id}",
    response_model=Application,
    status_code=http_status.HTTP_200_OK,
    summary="申請詳細取得",
    description="申請IDを指定して申請の詳細情報を取得します",
    responses={
        401: {"model": ErrorResponse, "description": "認証が必要です"},
        404: {"model": ErrorResponse, "description": "申請が見つかりません"},
        500: {"model": ErrorResponse, "description": "サーバーエラー"},
    },
)
async def get_application(
    id: str,
    db: Session = Depends(get_db_dependency),
    current_user: dict = Depends(get_current_user_dependency),
) -> Application:
    """申請IDで申請の詳細を取得します"""
    newrelic.agent.set_transaction_name('/v0.1/applications/{id}')
    
    try:
        # カスタム属性: 申請ID
        newrelic.agent.add_custom_attribute('application_id', id)
        user_id = current_user.get("user_id") or current_user.get("sub")
        newrelic.agent.add_custom_attribute('user_id', user_id)
        
        # トークンを取得（外部サービス呼び出し時に使用）
        token = current_user.get("_token")
        
        application = ApplicationService.get_application(db=db, application_id=id)
        if not application:
            newrelic.agent.add_custom_attribute('application_found', False)
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Application not found",
                    "message": "指定された申請IDの申請が見つかりません",
                },
            )
        
        # カスタム属性: 申請情報
        newrelic.agent.add_custom_attribute('application_found', True)
        newrelic.agent.add_custom_attribute('application_type', application.type)
        status_value = application.status.value if hasattr(application.status, 'value') else str(application.status)
        newrelic.agent.add_custom_attribute('application_status', status_value)
        newrelic.agent.add_custom_attribute('applicant_id', application.applicant_id)
        newrelic.agent.add_custom_attribute('application_current_step', application.current_step)
        newrelic.agent.add_custom_attribute('application_total_steps', application.total_steps)
        newrelic.agent.add_custom_attribute('application_next_approver_id', application.next_approver_id)

        # Pydanticモデルに変換
        app_dict = Application.model_validate(application).model_dump()

        # 最新コメント・経費精算のレシート画像一覧を取得
        if application.comments:
            latest_comment = max(application.comments, key=lambda c: c.created_at)
            app_dict["latestComment"] = latest_comment.body
        if application.receipt_images:
            app_dict["receiptImageUrls"] = [img.image_url for img in application.receipt_images]

        # 申請者名が設定されていない場合、UserServiceから取得
        if not app_dict.get("applicantName") and application.applicant_id:
            applicant_info = UserService.get_user_info(application.applicant_id, token)
            if applicant_info:
                app_dict["applicantName"] = applicant_info.get("name")
                app_dict["applicantDepartment"] = applicant_info.get("department")

        return Application(**app_dict)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_SERVER_ERROR", "message": str(e)},
        )

