"""Abstract base for parlay evaluation rules."""

from abc import ABC, abstractmethod

from src.parlay_rules.models import ParlayCandidate, RuleResult


class Rule(ABC):
    """A single pass/fail evaluation rule applied to a parlay candidate."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def evaluate(self, candidate: ParlayCandidate) -> RuleResult: ...
