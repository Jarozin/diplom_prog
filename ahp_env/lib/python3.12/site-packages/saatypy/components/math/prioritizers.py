from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
from saatypy.components.types import FloatArray

class PriorityStrategy(ABC):
    """ABC for computing a priority vector from a positive reciprocal matrix."""
    @abstractmethod
    def priorities(self, matrix: FloatArray) -> FloatArray: ...

class EigenvectorPriority(PriorityStrategy):
    """Principal-eigenvector method."""
    def priorities(self, matrix: FloatArray) -> FloatArray:
        vals, vecs = np.linalg.eig(matrix)
        i = int(np.argmax(np.real(vals)))
        v = np.real(vecs[:, i])
        v = abs(v)  # magnitudes
        v = v / v.sum()
        return v.astype(np.float64)

class GeometricMeanPriority(PriorityStrategy):
    """Geometric-mean-of-rows alternative."""
    def priorities(self, matrix: FloatArray) -> FloatArray:
        v = np.exp(np.log(matrix).mean(axis=1))
        v = v / v.sum()
        return v.astype(np.float64)
