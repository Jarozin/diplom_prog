from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple


from saatypy.components.types import Label, FloatArray



@dataclass(slots=True, kw_only=True)
class DecisionModel(ABC):
    """Shared base for decision models (AHP/ANP)."""

    cr_threshold: float = 0.10

    @abstractmethod
    def alternative_priorities(self) -> Tuple[FloatArray, List[Label]]: ...
    @abstractmethod
    def to_report_data(self) -> dict: ...
