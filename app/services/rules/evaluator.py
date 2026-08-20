from typing import List, Optional

from sqlalchemy.orm import Session
import newrelic.agent

from app.models.assertion_rule import AssertionRule
from app.services.rules.strategies import STRATEGY_MAP


def select_effective_rules(rules: List[AssertionRule]) -> List[AssertionRule]:
    """
    同一 order のルールが複数存在する場合（company_id一致行と、company_id=NULLの
    全社共通デフォルト行が両方マッチした場合）、company_id一致行を優先し、
    NULL行は無視する（チームが恒久対応でルールを上書きした場合の優先順位ロジック）。

    company_id一致行が存在しないorderについては、NULL行（デフォルト）がそのまま使われる。

    Args:
        rules: evaluate()のクエリ結果（company_id一致 or NULL の行が混在しうる）

    Returns:
        order昇順の、order毎に1行だけに絞り込んだルールのリスト
    """
    effective: dict = {}
    for rule in rules:
        current = effective.get(rule.order)
        if current is None:
            effective[rule.order] = rule
        elif current.company_id is None and rule.company_id is not None:
            # NULL行が先に採用されていた場合、company_id一致行が見つかれば差し替える
            effective[rule.order] = rule
        # 既にcompany_id一致行が採用されている場合、NULL行は無視する（何もしない）
    return [effective[order] for order in sorted(effective.keys())]


class AssertionRuleEvaluator:
    """
    DBに設定されたルール（Strategy Pattern）を使って申請フィールドの値を評価する。

    ルールに違反した場合、そのルールに設定された error_message を持つ
    ValidationError(error_code="ASSERTION_RULE_VIOLATION") を raise する。
    """

    def evaluate(
        self,
        application_type: str,
        target_field: str,
        value: str,
        company_id: Optional[str],
        db: Session,
    ) -> None:
        """
        指定された application_type / target_field に紐づく有効なルールを
        order順に評価する。company_id が一致する行、または company_id が
        NULL（全社共通のデフォルト）の行が対象になる。

        Args:
            application_type: 申請タイプ（例: 'promotion'）
            target_field: 検証対象フィールド名（例: 'description'）
            value: 検証対象の値
            company_id: 会社ID（チームごとのルール上書きの判定に使用）
            db: データベースセッション

        Raises:
            ValidationError: いずれかのルールに違反した場合
                (error_code="ASSERTION_RULE_VIOLATION")
        """
        # 循環importを避けるため、ここでimportする
        # (validation_service.py -> evaluator.py -> validation_service.py になるため)
        from app.services.validation_service import ValidationError

        rules = (
            db.query(AssertionRule)
            .filter(
                AssertionRule.application_type == application_type,
                AssertionRule.target_field == target_field,
                AssertionRule.is_active == True,  # noqa: E712
                (AssertionRule.company_id == company_id) | (AssertionRule.company_id.is_(None)),
            )
            .order_by(AssertionRule.order)
            .all()
        )

        # 同一orderでcompany_id一致行とNULL(共通デフォルト)行が両方マッチした場合、
        # company_id一致行を優先し、NULL行は評価しない（恒久対応の上書きを有効にするため）
        rules = select_effective_rules(rules)

        for rule in rules:
            prefix = f'assertion_rule{rule.order}'
            newrelic.agent.add_custom_attribute(f'{prefix}_id', rule.id)
            newrelic.agent.add_custom_attribute(f'{prefix}_type', rule.rule_type)
            newrelic.agent.add_custom_attribute(f'{prefix}_target_field', target_field)
            newrelic.agent.add_custom_attribute(f'{prefix}_value', value)

            result = STRATEGY_MAP[rule.rule_type].check(value, rule.config)
            newrelic.agent.add_custom_attribute(f'{prefix}_result', result)
            if not result:
                raise ValidationError(
                    error_code="ASSERTION_RULE_VIOLATION",
                    message=rule.error_message or "入力内容がルールに違反しています",
                    field=target_field,
                )
