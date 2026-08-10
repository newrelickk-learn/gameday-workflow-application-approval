from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class GameProgress(Base):
    """
    GameDay演習における仮想時間進行状態

    company_id（チーム）ごとに、実際の現在時刻からのオフセット日数
    （virtual_date_offset_days）を管理する。company_idにユニーク制約はなく、
    「現在の進行状態」は常に company_id + is_active=true の1行として扱う。
    バックエンドの実際の検証には一切使わず、フロントエンドの「仮想今日」表示
    （getVirtualToday()）にのみ使用される。
    """
    __tablename__ = "game_progress"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, nullable=False, index=True)
    virtual_date_offset_days = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
