from abc import ABC, abstractmethod


class RuleStrategy(ABC):
    """
    申請フィールド検証ルールのStrategy抽象基底クラス

    AssertionRule.rule_type ごとに具象クラスを実装し、
    STRATEGY_MAP（app.services.rules.strategies）経由で選択される。
    """

    @abstractmethod
    def check(self, value: str, config: dict) -> bool:
        """
        値がルールを満たすかどうかを判定します

        Args:
            value: 検証対象の値
            config: ルールタイプ毎のパラメータ（AssertionRule.config）

        Returns:
            ルールを満たす場合True
        """
        ...
