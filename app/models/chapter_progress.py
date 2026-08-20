from sqlalchemy import Column, String, Integer, Date, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class ChapterProgress(Base):
    """
    GameDay演習における章クリア状態（第2章・第4章などの原因診断ドロップダウン）

    company_id + chapterごとに1行のみを保持し、正解を出すたびに cleared_date を
    その時点のUTC日付でUPSERTする。「進捗は当日のみ有効」という要件は、
    cleared_date = 今日のUTC日付 かどうかで判定する（日付が変われば、行を消さずに
    自動的に「未クリア」扱いに戻る）。
    """
    __tablename__ = "chapter_progress"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    chapter = Column(Integer, nullable=False)
    cleared_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
