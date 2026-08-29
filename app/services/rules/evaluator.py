import json
from typing import List, Optional

from sqlalchemy.orm import Session
import newrelic.agent

from app.models.assertion_rule import AssertionRule
from app.services.rules.strategies import STRATEGY_MAP


def select_effective_rules(rules: List[AssertionRule]) -> List[AssertionRule]:
    effective: dict = {}
    for rule in rules:
        current = effective.get(rule.order)
        if current is None:
            effective[rule.order] = rule
        elif current.company_id is None and rule.company_id is not None:
            effective[rule.order] = rule
    return [effective[order] for order in sorted(effective.keys())]


class AssertionRuleEvaluator:

    def evaluate(
        self,
        application_type: str,
        target_field: str,
        value: str,
        company_id: Optional[str],
        db: Session,
    ) -> None:
        from app.services.validation_service import ValidationError

        rules = (
            db.query(AssertionRule)
            .filter(
                AssertionRule.application_type == application_type,
                AssertionRule.target_field == target_field,
                AssertionRule.is_active == True,  
                (AssertionRule.company_id == company_id) | (AssertionRule.company_id.is_(None)),
            )
            .order_by(AssertionRule.order)
            .all()
        )

        rules = select_effective_rules(rules)

        for rule in rules:
            prefix = f'assertion_rule{rule.order}'
            newrelic.agent.add_custom_attribute(f'{prefix}_id', rule.id)
            newrelic.agent.add_custom_attribute(f'{prefix}_type', rule.rule_type)
            newrelic.agent.add_custom_attribute(f'{prefix}_target_field', target_field)
            newrelic.agent.add_custom_attribute(f'{prefix}_config', json.dumps(rule.config))
            newrelic.agent.add_custom_attribute(f'{prefix}_value', value)

            result = STRATEGY_MAP[rule.rule_type].check(value, rule.config)
            newrelic.agent.add_custom_attribute(f'{prefix}_result', result)
            if not result:
                raise ValidationError(
                    error_code="ASSERTION_RULE_VIOLATION",
                    message=rule.error_message or "入力内容がルールに違反しています",
                    field=target_field,
                )
