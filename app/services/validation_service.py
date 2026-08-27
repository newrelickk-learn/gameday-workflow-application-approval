from typing import Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models.application import ApplicationType
from app.schemas.application import CreateApplicationRequest
from app.services.user_service import UserService
from app.services.rules.evaluator import AssertionRuleEvaluator
from app.services.game_progress_service import GameProgressService
from app.services.chapter_progress_service import ChapterProgressService

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
                    message="プロモーション申請は上長のみが申請可能です",
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
                    message="開始日は必須です",
                    field="startDate"
                )
            if not end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message="終了日は必須です",
                    field="endDate"
                )
            
            if start_date > end_date:
                raise ValidationError(
                    error_code="INVALID_DATE_RANGE",
                    message="開始日は終了日以前である必要があります",
                    field="startDate"
                )
            
            if application_type == ApplicationType.BUSINESS_TRIP.value:
                today = virtual_today if virtual_today is not None else date.today()
                min_start_date = today + timedelta(days=ValidationService.BUSINESS_TRIP_MIN_ADVANCE_DAYS)
                
                if start_date < min_start_date:
                    raise ValidationError(
                        error_code="INSUFFICIENT_ADVANCE_NOTICE",
                        message="出張申請は開始日の2週間前までに申請する必要があります",
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
                    message="出張申請には開始日が必要です",
                    field="startDate"
                )
            if not data.end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message="出張申請には終了日が必要です",
                    field="endDate"
                )
        
        elif application_type == ApplicationType.EXPENSE.value:
            if data.amount is None:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message="経費申請には金額が必要です",
                    field="amount"
                )
        
        elif application_type == ApplicationType.VACATION.value:
            if not data.start_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message="有給休暇申請には開始日が必要です",
                    field="startDate"
                )
            if not data.end_date:
                raise ValidationError(
                    error_code="MISSING_REQUIRED_FIELD",
                    message="有給休暇申請には終了日が必要です",
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
                    message="金額は正の数である必要があります",
                    field="amount"
                )
        
        if data.days is not None:
            if data.days <= 0:
                raise ValidationError(
                    error_code="INVALID_DAYS",
                    message="日数は正の数である必要があります",
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
    def validate_application(
        data: CreateApplicationRequest,
        user_id: str,
        token: Optional[str] = None,
        db: Optional[Session] = None
    ) -> None:
        ValidationService.validate_application_type(data.type, user_id, token)

        ValidationService.validate_required_fields(data.type, data)

        virtual_today = None
        if data.type == ApplicationType.BUSINESS_TRIP.value and db is not None:
            company_id = ValidationService._resolve_company_id(user_id, token)
            if company_id:
                progress = GameProgressService.get_active_progress(db, company_id)
                if progress is not None:
                    virtual_today = date.today() + timedelta(days=progress.virtual_date_offset_days)
        ValidationService.validate_dates(data.type, data.start_date, data.end_date, virtual_today)

        ValidationService.validate_business_rules(data)

        if data.type != ApplicationType.PROMOTION.value and data.applicant_id != user_id:
            raise ValidationError(
                error_code="INVALID_APPLICANT_ID",
                message="申請者IDは現在のユーザーIDと一致する必要があります",
                field="applicantId"
            )

        if data.type == ApplicationType.PROMOTION.value and db is not None:
            company_id = ValidationService._resolve_company_id(user_id, token)

            if company_id:
                cleared_today = set(ChapterProgressService.get_cleared_chapters_today(db, company_id))
                missing = [c for c in PROMOTION_PREREQUISITE_CHAPTERS if c not in cleared_today]
                if missing:
                    missing_label = "、".join(f"第{c}章" for c in missing)
                    raise ValidationError(
                        error_code="PREREQUISITE_CHAPTERS_NOT_CLEARED",
                        message=f"プロモーション申請を行うには、先に第0〜4章をすべてクリアする必要があります（未クリア: {missing_label}）",
                        field="type",
                    )

            AssertionRuleEvaluator().evaluate(
                application_type=data.type,
                target_field="description",
                value=data.description,
                company_id=company_id,
                db=db,
            )

