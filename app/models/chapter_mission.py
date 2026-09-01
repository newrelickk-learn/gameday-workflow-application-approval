from sqlalchemy import Column, String, Integer, Boolean

from app.db.base import Base


class ChapterMission(Base):
    __tablename__ = "chapter_missions"

    id = Column(String, primary_key=True, index=True)
    chapter = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    order = Column(Integer, nullable=False, default=0, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    clear_keyword = Column(String, nullable=True)
