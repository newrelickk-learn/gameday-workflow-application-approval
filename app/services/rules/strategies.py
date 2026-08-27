import re

from app.services.rules.base import RuleStrategy


class RegexPatternStrategy(RuleStrategy):

    def check(self, value: str, config: dict) -> bool:
        return bool(re.search(config["pattern"], value))


class MinLengthStrategy(RuleStrategy):

    def check(self, value: str, config: dict) -> bool:
        return len(value) >= config["min_length"]


class MaxLengthStrategy(RuleStrategy):

    def check(self, value: str, config: dict) -> bool:
        return len(value) <= config["max_length"]


class ForbiddenWordsStrategy(RuleStrategy):

    def check(self, value: str, config: dict) -> bool:
        return not any(w in value for w in config["forbidden_words"])


class RequiredKeywordStrategy(RuleStrategy):

    def check(self, value: str, config: dict) -> bool:
        return config["keyword"] in value


STRATEGY_MAP = {
    "regex_pattern": RegexPatternStrategy(),
    "min_length": MinLengthStrategy(),
    "max_length": MaxLengthStrategy(),
    "forbidden_words": ForbiddenWordsStrategy(),
    "required_keyword": RequiredKeywordStrategy(),
}
