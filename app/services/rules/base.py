from abc import ABC, abstractmethod


class RuleStrategy(ABC):

    @abstractmethod
    def check(self, value: str, config: dict) -> bool:
        ...
