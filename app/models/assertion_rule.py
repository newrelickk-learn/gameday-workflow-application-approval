from sqlalchemy import Column, String, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class AssertionRule(Base):
    """
    申請フィールドの検証ルール定義（Strategy Pattern + DB設定）

    プロモーション申請の description（例: "L3->L4"）のような、
    申請タイプ・対象フィールドごとの検証ルールをDBで管理する。
    実際の評価は app.services.rules.evaluator.AssertionRuleEvaluator が行う。
    """
    __tablename__ = "assertion_rules"

    id = Column(String, primary_key=True, index=True)
    application_type = Column(String, nullable=False, index=True)
    target_field = Column(String, nullable=False)
    # 'regex_pattern' | 'min_length' | 'max_length' | 'forbidden_words' | 'required_keyword'
    rule_type = Column(String, nullable=False)
    # ルールタイプ毎のパラメータ（例: {"pattern": "..."}）
    # PostgreSQLではJSONBとして保存されるが、テスト用SQLite等でも動作するようJSONにフォールバックする
    config = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    # ルール違反時にValidationError.messageとして返されるメッセージ
    error_message = Column(String, nullable=True)
    # 適用順（同一 application_type/target_field 内で順に評価）
    order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    # NULL可。NULLなら全社共通のデフォルト。チームごとの恒久対応でここを更新する
    company_id = Column(String, nullable=True, index=True)
