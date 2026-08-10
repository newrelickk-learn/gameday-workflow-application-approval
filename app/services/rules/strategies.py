import re

from app.services.rules.base import RuleStrategy


class RegexPatternStrategy(RuleStrategy):
    """正規表現パターンにマッチするかを検証するルール（今回のシードで使用）"""

    def check(self, value: str, config: dict) -> bool:
        return bool(re.search(config["pattern"], value))


class MinLengthStrategy(RuleStrategy):
    """最小文字数を満たすかを検証するルール（ダミー、DB未登録）"""

    def check(self, value: str, config: dict) -> bool:
        return len(value) >= config["min_length"]


class MaxLengthStrategy(RuleStrategy):
    """最大文字数を超えていないかを検証するルール（ダミー、DB未登録）"""

    def check(self, value: str, config: dict) -> bool:
        return len(value) <= config["max_length"]


class ForbiddenWordsStrategy(RuleStrategy):
    """禁止語を含んでいないかを検証するルール（ダミー、DB未登録）"""

    def check(self, value: str, config: dict) -> bool:
        return not any(w in value for w in config["forbidden_words"])


class RequiredKeywordStrategy(RuleStrategy):
    """必須キーワードを含んでいるかを検証するルール（ダミー、DB未登録）"""

    def check(self, value: str, config: dict) -> bool:
        return config["keyword"] in value


# AssertionRule.rule_type -> Strategyインスタンスのマッピング
STRATEGY_MAP = {
    "regex_pattern": RegexPatternStrategy(),
    "min_length": MinLengthStrategy(),
    "max_length": MaxLengthStrategy(),
    "forbidden_words": ForbiddenWordsStrategy(),
    "required_keyword": RequiredKeywordStrategy(),
}
