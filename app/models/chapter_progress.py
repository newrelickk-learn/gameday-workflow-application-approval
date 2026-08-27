from sqlalchemy import Column, String, Integer, Date, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class ChapterProgress(Base):
    __tablename__ = "chapter_progress"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    chapter = Column(Integer, nullable=False)
    cleared_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
