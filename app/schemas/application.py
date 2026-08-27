from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.application import ApplicationStatus


class ApplicationBase(BaseModel):
    type: str = Field(..., description="申請タイプ（business-trip, expense, vacation, promotion等）")
    title: str = Field(..., description="申請タイトル")
    description: str = Field(..., description="申請内容の説明")
    amount: Optional[float] = Field(None, description="金額（経費精算の場合）")
    start_date: Optional[date] = Field(None, alias="startDate", description="開始日（有給休暇・出張の場合）")
    end_date: Optional[date] = Field(None, alias="endDate", description="終了日（有給休暇・出張の場合）")
    days: Optional[int] = Field(None, description="日数（有給休暇・出張の場合）")
    applicant_id: str = Field(..., alias="applicantId", description="申請者ID")
    
    model_config = ConfigDict(populate_by_name=True)


class CreateApplicationRequest(ApplicationBase):
    dependency_chain: Optional[List[str]] = Field(
        None,
        alias="dependencyChain",
        description="経費申請: サービス依存関係チェーンの回答（任意）",
    )
    departure_city_name: Optional[str] = Field(
        None,
        alias="departureCityName",
        description="出張申請: 出発地の都市名（任意。都市IDはtravelサービス側のSERIAL連番でブレるため名前で判定する）",
    )
    arrival_city_name: Optional[str] = Field(
        None,
        alias="arrivalCityName",
        description="出張申請: 到着地の都市名（任意）",
    )


class Application(ApplicationBase):
    id: str = Field(..., description="申請ID")
    application_number: Optional[str] = Field(None, alias="applicationNumber", description="申請書番号（例: BT-000001）")
    status: ApplicationStatus = Field(..., description="申請ステータス")
    applicant_name: Optional[str] = Field(None, alias="applicantName", description="申請者名（表示用）")
    applicant_department: Optional[str] = Field(None, alias="applicantDepartment", description="申請者所属（表示用）")
    current_step: Optional[int] = Field(None, alias="currentStep", description="現在の承認ステップ")
    total_steps: Optional[int] = Field(None, alias="totalSteps", description="総承認ステップ数")
    next_approver_id: Optional[str] = Field(None, alias="nextApproverId", description="次の承認者ID")
    next_approver_name: Optional[str] = Field(None, alias="nextApproverName", description="次の承認者名（表示用）")
    next_approver_department: Optional[str] = Field(None, alias="nextApproverDepartment", description="次の承認者所属（表示用）")
    latest_comment: Optional[str] = Field(None, alias="latestComment", description="最新のコメント本文（表示用）")
    receipt_image_urls: Optional[List[str]] = Field(None, alias="receiptImageUrls", description="経費精算のレシート画像URL一覧（表示用）")
    created_at: datetime = Field(..., alias="createdAt", description="作成日時")
    updated_at: datetime = Field(..., alias="updatedAt", description="更新日時")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            date: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        },
    )


class ErrorResponse(BaseModel):
    error: str = Field(..., description="エラーコード")
    message: Optional[str] = Field(None, description="エラーメッセージ")


class ValidationErrorResponse(BaseModel):
    error: str = Field(..., description="エラーコード")
    message: str = Field(..., description="エラーメッセージ")
    field: Optional[str] = Field(None, description="エラーが発生したフィールド名")

