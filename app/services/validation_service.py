from typing import Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models.application import ApplicationType
from app.core.i18n import t
from app.schemas.application import CreateApplicationRequest
from app.services.user_service import UserService
from app.services.rules.evaluator import AssertionRuleEvaluator
from app.services.game_master_tokens import GameState
from app.services.ai_review_service import AiReviewService

PROMOTION_PREREQUISITE_CHAPTERS = [0, 1, 2, 3, 4]


class ValidationError(Exception):
    def __init__(self, error_code: str, message: str, field: Optional[str] = None):
        self.error_code = error_code
        self.message = message
        self.field = field
        super().__init__(self.message)


class ValidationService:
    
    BUSINESS_TRIP_MIN_ADVANCE_DAYS = 14
    
    @staticmethod
    def validate_application_type(
        application_type: str,
        user_id: str,
        token: Optional[str] = None
    ) -> None:
        try:
            app_type = ApplicationType(application_type)
        except ValueError:
            valid_types = [t.value for t in ApplicationType]
            raise ValidationError(
                error_code="INVALID_APPLICATION_TYPE",
                message=f"申請タイプが不正です。有効なタイプ: {', '.join(valid_types)}",
                field="type"
            )
        
        if app_type == ApplicationType.PROMOTION:
            if not UserService.is_manager(user_id, token):
                raise ValidationError(
                    error_code="PERMISSION_DENIED",
                    message=t("promotion_manager_only"),
                    field="type"
                )
    
    @staticmethod
    def validate_dates(
        application_type: str,
        start_date: Optional[date],
        end_date: Optional[date],
        virtual_today: Optional[date] = None
    ) -> None:
        if application_type in [ApplicationType.BUSINESS_TRIP.value, ApplicationType.VACATION.value]:
            if not start_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("start_date_required"),
                    field="startDate"
                )
            if not end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("end_date_required"),
                    field="endDate"
                )
            
            if start_date > end_date:
                raise ValidationError(
                    error_code="INVALID_DATE_RANGE",
                    message=t("start_after_end"),
                    field="startDate"
                )
            
            if application_type == ApplicationType.BUSINESS_TRIP.value:
                today = virtual_today if virtual_today is not None else date.today()
                min_start_date = today + timedelta(days=ValidationService.BUSINESS_TRIP_MIN_ADVANCE_DAYS)
                
                if start_date < min_start_date:
                    raise ValidationError(
                        error_code="INSUFFICIENT_ADVANCE_NOTICE",
                        message=t("business_trip_advance_notice"),
                        field="startDate"
                    )
    
    @staticmethod
    def validate_required_fields(
        application_type: str,
        data: CreateApplicationRequest
    ) -> None:
        if application_type == ApplicationType.BUSINESS_TRIP.value:
            if not data.start_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("business_trip_start_date_required"),
                    field="startDate"
                )
            if not data.end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("business_trip_end_date_required"),
                    field="endDate"
                )
        
        elif application_type == ApplicationType.EXPENSE.value:
            if data.amount is None:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("expense_amount_required"),
                    field="amount"
                )
        
        elif application_type == ApplicationType.VACATION.value:
            if not data.start_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("vacation_start_date_required"),
                    field="startDate"
                )
            if not data.end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message=t("vacation_end_date_required"),
                    field="endDate"
                )
    
    @staticmethod
    def validate_business_rules(
        data: CreateApplicationRequest
    ) -> None:
        if data.amount is not None:
            if data.amount <= 0:
                raise ValidationError(
                    error_code="INVALID_AMOUNT",
                    message=t("amount_must_be_positive"),
                    field="amount"
                )
        
        if data.days is not None:
            if data.days <= 0:
                raise ValidationError(
                    error_code="INVALID_DAYS",
                    message=t("days_must_be_positive"),
                    field="days"
                )
    
    @staticmethod
    def _resolve_company_id(user_id: str, token: Optional[str] = None) -> Optional[str]:
        user_info = UserService.get_user_info(user_id, token)
        if not user_info:
            return None
        company_id = user_info.get("CompanyId") or user_info.get("companyId")
        if company_id is None:
            return None
        return str(company_id)

    @staticmethod
    def validate_ai_review(data: CreateApplicationRequest) -> None:
        """出張申請の説明文をAIレビュアーに確認してもらう。

        目的・訪問先・業務内容が具体的に書かれていない申請は差し戻す。
        AWS側の障害時はAiReviewServiceが通す側に倒すため、ここでは結果をそのまま使う。
        """
        result = AiReviewService.review_business_trip(
            title=data.title,
            description=data.description,
            departure_city_name=data.departure_city_name,
            arrival_city_name=data.arrival_city_name,
        )
        if not result.approved:
            raise ValidationError(
                error_code="AI_REVIEW_REJECTED",
                message=result.reason or AiReviewService.fallback_reason(),
                field="description",
            )

    @staticmethod
    def validate_application(
        data: CreateApplicationRequest,
        user_id: str,
        db: Session,
        token: Optional[str] = None,
        game_state: Optional[GameState] = None,
    ) -> None:
        """game_stateはfrontendがgame-masterから取得して添えてきたスナップショット。
        取得・検証できなかった場合はNoneで、game-masterに問い合わせられなかったときと同じ扱いになる
        (仮想日付は実際の今日、クリア済みの章はなし)。
        """
        ValidationService.validate_application_type(data.type, user_id, token)

        ValidationService.validate_required_fields(data.type, data)

        virtual_today = None
        if data.type == ApplicationType.BUSINESS_TRIP.value:
            if game_state is not None:
                virtual_today = date.today() + timedelta(days=game_state.virtual_date_offset_days)
        ValidationService.validate_dates(data.type, data.start_date, data.end_date, virtual_today)

        ValidationService.validate_business_rules(data)

        if data.type == ApplicationType.BUSINESS_TRIP.value:
            ValidationService.validate_ai_review(data)

        if data.type != ApplicationType.PROMOTION.value and data.applicant_id != user_id:
            raise ValidationError(
                error_code="INVALID_APPLICANT_ID",
                message=t("applicant_mismatch"),
                field="applicantId"
            )

        if data.type == ApplicationType.PROMOTION.value:
            cleared_today = set(game_state.cleared_chapters) if game_state is not None else set()
            missing = [c for c in PROMOTION_PREREQUISITE_CHAPTERS if c not in cleared_today]
            if missing:
                raise ValidationError(
                    error_code="PREREQUISITE_CHAPTERS_NOT_CLEARED",
                    message=f"プロモーション申請を行うには、先に他{len(missing)}個の問題をすべてクリアする必要があります",
                    field="type",
                )

            company_id = ValidationService._resolve_company_id(user_id, token)
            AssertionRuleEvaluator().evaluate(
                application_type=data.type,
                target_field="description",
                value=data.description,
                company_id=company_id,
                db=db,
            )

