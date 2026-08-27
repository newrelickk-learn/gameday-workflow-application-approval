from sqlalchemy import Column, String, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class AssertionRule(Base):
    __tablename__ = "assertion_rules"

    id = Column(String, primary_key=True, index=True)
    application_type = Column(String, nullable=False, index=True)
    target_field = Column(String, nullable=False)
    rule_type = Column(String, nullable=False)
    config = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    error_message = Column(String, nullable=True)
    order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    company_id = Column(String, nullable=True, index=True)
