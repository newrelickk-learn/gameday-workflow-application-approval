from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.base import Base


class ApplicationType(str, enum.Enum):
    """申請タイプ"""
    BUSINESS_TRIP = "business-trip"
    EXPENSE = "expense"
    VACATION = "vacation"
    PROMOTION = "promotion"
    
    @property
    def display_name(self) -> str:
        """申請タイプの表示名を返す"""
        mapping = {
            ApplicationType.BUSINESS_TRIP: "出張申請",
            ApplicationType.EXPENSE: "経費申請",
            ApplicationType.VACATION: "有給休暇申請",
            ApplicationType.PROMOTION: "プロモーション申請",
        }
        return mapping.get(self, self.value)


class ApplicationStatus(str, enum.Enum):
    """申請ステータス"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Application(Base):
    """申請モデル"""
    __tablename__ = "applications"

    id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    
    # オプショナルフィールド
    amount = Column(Float, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    days = Column(Integer, nullable=True)
    
    # ステータス（String型として保存）
    status = Column(
        String(20),
        nullable=False,
        default=ApplicationStatus.PENDING.value,  # Enumの値を明示的に使用
        index=True
    )
    
    # 申請者情報
    applicant_id = Column(String, nullable=False, index=True)
    applicant_name = Column(String, nullable=True)
    applicant_department = Column(String, nullable=True)

    # 申請者の所属会社ID。承認者向け一覧（GET /applications、applicantId未指定時）を
    # 自社分だけにDBレベルで絞り込むために使う（以前はcompany_idでのSQLフィルタが無く、
    # 全社分をLIMIT 1000で一括取得してからPythonループで絞り込んでいたため、データ量が
    # 増えるとN+1ループの対象行数が肥大化しPodのliveness probeタイムアウトを引き起こした）。
    company_id = Column(Integer, nullable=True, index=True)

    # 申請書番号（タイプ別Prefix + 6桁ゼロ埋め連番、例: BT-000001）。
    # 【意図的な障害シード】検索用インデックスを意図的に貼らない(index=False明示)。
    # 新機能として追加した際にインデックスを貼り忘れ、大量データでの番号検索が
    # company_idの絞り込み後に線形フィルタになる、というGameDayシナリオのため。
    application_number = Column(String, nullable=True, index=False)

    # 承認フロー情報
    current_step = Column(Integer, nullable=True)
    total_steps = Column(Integer, nullable=True)
    next_approver_id = Column(String, nullable=True)
    next_approver_name = Column(String, nullable=True)
    next_approver_department = Column(String, nullable=True)
    
    # タイムスタンプ
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 申請コメント（1対多）。lazy="select"（デフォルト）のまま明示することで、
    # 一覧取得時にアクセスすると申請ごとに個別SELECTが発行される（意図的なN+1）。
    comments = relationship("ApplicationComment", lazy="select")

    # 経費精算のレシート画像（1対多）
    receipt_images = relationship("ApplicationReceiptImage", lazy="select")


class ApplicationNumberCounter(Base):
    """申請書番号の連番管理用カウンターテーブル（会社×タイプごとに1行。
    連番は会社ごとに独立してリセットされる）"""
    __tablename__ = "application_number_counters"

    company_id = Column(Integer, primary_key=True, index=True)
    application_type = Column(String, primary_key=True, index=True)
    last_number = Column(Integer, nullable=False, default=0)


class ApplicationComment(Base):
    """申請コメントモデル"""
    __tablename__ = "application_comments"

    id = Column(String, primary_key=True, index=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    author_name = Column(String, nullable=True)
    body = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApplicationReceiptImage(Base):
    """経費精算のレシート画像モデル"""
    __tablename__ = "application_receipt_images"

    id = Column(String, primary_key=True, index=True)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False, index=True)
    image_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
