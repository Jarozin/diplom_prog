from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from saatypy.components.types import Label

@dataclass(slots=True, frozen=True)
class Node:
    """An individual element inside a cluster (compared in PCs)."""
    name: Label
    description: str = ""

@dataclass(slots=True)
class Cluster:
    """A group of related nodes that define supermatrix blocks."""
    name: Label
    nodes: List[Node]
    weight: Optional[float] = None

    def __post_init__(self) -> None:
        names = [n.name for n in self.nodes]
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate node names in cluster '{self.name}'")

    @property
    def size(self) -> int:
        return len(self.nodes)
