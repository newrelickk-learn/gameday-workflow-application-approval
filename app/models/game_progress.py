from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class GameProgress(Base):
    __tablename__ = "game_progress"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    virtual_date_offset_days = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
