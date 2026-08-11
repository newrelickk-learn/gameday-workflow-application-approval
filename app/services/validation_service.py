from typing import Optional
from datetime import date, datetime, timedelta
from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.application import ApplicationType
from app.schemas.application import CreateApplicationRequest
from app.services.user_service import UserService
from app.services.rules.evaluator import AssertionRuleEvaluator
from app.services.game_progress_service import GameProgressService


class ValidationError(Exception):
    """バリデーションエラー"""
    def __init__(self, error_code: str, message: str, field: Optional[str] = None):
        self.error_code = error_code
        self.message = message
        self.field = field
        super().__init__(self.message)


class ValidationService:
    """申請バリデーションサービス"""
    
    # 出張申請の最低申請期間（日数）
    BUSINESS_TRIP_MIN_ADVANCE_DAYS = 14
    
    @staticmethod
    def validate_application_type(
        application_type: str,
        user_id: str,
        token: Optional[str] = None
    ) -> None:
        """
        申請タイプとユーザー権限をチェックします
        
        Args:
            application_type: 申請タイプ
            user_id: ユーザーID
            
        Raises:
            ValidationError: バリデーションエラー時
        """
        # 申請タイプの存在チェック
        try:
            app_type = ApplicationType(application_type)
        except ValueError:
            valid_types = [t.value for t in ApplicationType]
            raise ValidationError(
                error_code="INVALID_APPLICATION_TYPE",
                message=f"申請タイプが不正です。有効なタイプ: {', '.join(valid_types)}",
                field="type"
            )
        
        # プロモーション申請は上長のみが申請可能
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
        """
        日付のバリデーションを行います

        Args:
            application_type: 申請タイプ
            start_date: 開始日
            end_date: 終了日
            virtual_today: 出張申請の2週間前チェックに使う「今日」。
                GameDayの演習用に、company_idのgame_progress.virtual_date_offset_days
                を反映した仮想の今日を渡す。未指定の場合は実際の今日にフォールバックする。

        Raises:
            ValidationError: バリデーションエラー時
        """
        # 開始日と終了日の存在チェック（日付が必要な申請タイプの場合）
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
            
            # 開始日 < 終了日のチェック
            if start_date >= end_date:
                raise ValidationError(
                    error_code="INVALID_DATE_RANGE",
                    message="開始日は終了日より前である必要があります",
                    field="startDate"
                )
            
            # 出張申請の2週間前チェック
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
        """
        必須フィールドのチェックを行います
        
        Args:
            application_type: 申請タイプ
            data: 申請データ
            
        Raises:
            ValidationError: バリデーションエラー時
        """
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
        """
        その他のビジネスルールチェックを行います
        
        Args:
            data: 申請データ
            
        Raises:
            ValidationError: バリデーションエラー時
        """
        # 金額が指定されている場合、正の数であること
        if data.amount is not None:
            if data.amount <= 0:
                raise ValidationError(
                    error_code="INVALID_AMOUNT",
                    message="金額は正の数である必要があります",
                    field="amount"
                )
        
        # 日数が指定されている場合、正の数であること
        if data.days is not None:
            if data.days <= 0:
                raise ValidationError(
                    error_code="INVALID_DAYS",
                    message="日数は正の数である必要があります",
                    field="days"
                )
    
    @staticmethod
    def _resolve_company_id(user_id: str, token: Optional[str] = None) -> Optional[str]:
        """
        ユーザーIDからCompanyIdを解決します
        （assertion_rulesのcompany_idスコープ判定に使用）

        Args:
            user_id: ユーザーID
            token: 認証トークン（オプション、外部サービス呼び出し時に使用）

        Returns:
            CompanyIdの文字列表現、取得できない場合はNone
        """
        user_info = UserService.get_user_info(user_id, token)
        if not user_info:
            return None
        # PascalCase (CompanyId) と camelCase (companyId) の両方に対応
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
        """
        申請データの全バリデーションを実行します

        Args:
            data: 申請データ
            user_id: ユーザーID
            token: 認証トークン（オプション、外部サービス呼び出し時に使用）
            db: データベースセッション（オプション、プロモーション申請のDB設定ルール評価に使用）

        Raises:
            ValidationError: バリデーションエラー時
            AssertionError: プロモーション申請のdescriptionがDB設定ルールに違反した場合
        """
        # 申請タイプのバリデーション
        ValidationService.validate_application_type(data.type, user_id, token)

        # 必須フィールドのチェック
        ValidationService.validate_required_fields(data.type, data)

        # 日付のバリデーション
        # 出張申請の2週間前チェックは、GameDayの演習用にcompany_idのgame_progressが
        # 管理する仮想の今日を基準に行う（company_id/game_progressが取得できない場合は
        # 実際の今日にフォールバックする）
        virtual_today = None
        if data.type == ApplicationType.BUSINESS_TRIP.value and db is not None:
            company_id = ValidationService._resolve_company_id(user_id, token)
            if company_id:
                progress = GameProgressService.get_active_progress(db, company_id)
                if progress is not None:
                    virtual_today = date.today() + timedelta(days=progress.virtual_date_offset_days)
        ValidationService.validate_dates(data.type, data.start_date, data.end_date, virtual_today)

        # その他のビジネスルールチェック
        ValidationService.validate_business_rules(data)

        # 申請者IDが現在のユーザーIDと一致すること（セキュリティ）
        # プロモーション申請は、上長が部下（プロモーション対象者）の代わりに送信するケースが
        # 正常フローのため対象外とする（validate_application_type内のis_managerチェックで、
        # ログイン中のユーザー自身が上長であることは既に保証されている）。
        # 経費・出張・休暇申請など、申請者本人が送信する他の申請タイプでは引き続き必須。
        if data.type != ApplicationType.PROMOTION.value and data.applicant_id != user_id:
            raise ValidationError(
                error_code="INVALID_APPLICANT_ID",
                message="申請者IDは現在のユーザーIDと一致する必要があります",
                field="applicantId"
            )

        # プロモーション申請の場合、descriptionに対してDB設定ルール（Strategy Pattern）を評価する。
        # 既存のis_managerチェック（validate_application_type内）に加えて実施する。
        if data.type == ApplicationType.PROMOTION.value and db is not None:
            company_id = ValidationService._resolve_company_id(user_id, token)
            AssertionRuleEvaluator().evaluate(
                application_type=data.type,
                target_field="description",
                value=data.description,
                company_id=company_id,
                db=db,
            )

