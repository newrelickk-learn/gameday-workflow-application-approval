from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from app.db.base import Base


class ApplicationType(str, enum.Enum):
    BUSINESS_TRIP = "business-trip"
    EXPENSE = "expense"
    VACATION = "vacation"
    PROMOTION = "promotion"
    
    @property
    def display_name(self) -> str:
        mapping = {
            ApplicationType.BUSINESS_TRIP: "出張申請",
            ApplicationType.EXPENSE: "経費申請",
            ApplicationType.VACATION: "有給休暇申請",
            ApplicationType.PROMOTION: "プロモーション申請",
        }
        return mapping.get(self, self.value)


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApplicationStatus.PENDING.value,  
        index=True
    )

    applicant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    applicant_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    applicant_department: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    application_number: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=False)

    current_step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_steps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_approver_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_approver_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_approver_department: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    comments: Mapped[List["ApplicationComment"]] = relationship("ApplicationComment", lazy="select")

    receipt_images: Mapped[List["ApplicationReceiptImage"]] = relationship("ApplicationReceiptImage", lazy="select")


class ApplicationNumberCounter(Base):
    __tablename__ = "application_number_counters"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_type: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ApplicationComment(Base):
    __tablename__ = "application_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"), nullable=False, index=True)
    author_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApplicationReceiptImage(Base):
    __tablename__ = "application_receipt_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String, ForeignKey("applications.id"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
