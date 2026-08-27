from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
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

    id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    
    amount = Column(Float, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    days = Column(Integer, nullable=True)
    
    status = Column(
        String(20),
        nullable=False,
        default=ApplicationStatus.PENDING.value,  
        index=True
    )
    
    applicant_id = Column(String, nullable=False, index=True)
    applicant_name = Column(String, nullable=True)
    applicant_department = Column(String, nullable=True)

    company_id = Column(Integer, nullable=True, index=True)

    application_number = Column(String, nullable=True, index=False)

    current_step = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=True)
    next_approver_id = Column(String, nullable=True)
    next_approver_name = Column(String, nullable=True)
    next_approver_department = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    comments = relationship("ApplicationComment", lazy="select")

    receipt_images = relationship("ApplicationReceiptImage", lazy="select")


class ApplicationNumberCounter(Base):
    __tablename__ = "application_number_counters"

    company_id = Column(Integer, primary_key=True, index=True)
    application_type = Column(String, primary_key=True, index=True)
    last_number = Column(Integer, nullable=False, default=0)


class ApplicationComment(Base):
    __tablename__ = "application_comments"

    id = Column(String, primary_key=True, index=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    author_name = Column(String, nullable=True)
    body = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApplicationReceiptImage(Base):
    __tablename__ = "application_receipt_images"

    id = Column(String, primary_key=True, index=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    image_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
