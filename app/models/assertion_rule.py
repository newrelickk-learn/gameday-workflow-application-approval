from typing import Any, Optional

from sqlalchemy import String, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssertionRule(Base):
    __tablename__ = "assertion_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    application_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_field: Mapped[str] = mapped_column(String, nullable=False)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[Any] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    company_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
