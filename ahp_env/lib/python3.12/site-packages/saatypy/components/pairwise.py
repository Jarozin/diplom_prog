from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
import numpy as np

from saatypy.components.types import Label, Judgment, FloatArray
from saatypy.components.scale import SaatyScale, RI_TABLE as _RI


class ConsistencyMixin:
    """Adds cached λmax / CI / CR properties for pairwise matrices."""

    _cache_evec: Optional[FloatArray] = field(default=None, init=False, repr=False)
    _cache_lambda_max: Optional[float] = None
    _cache_ci: Optional[float] = None
    _cache_cr: Optional[float] = None
    labels: List[Label]
    matrix: FloatArray

    @property
    def lambda_max(self) -> float:  
        if self._cache_lambda_max is None:
            lam, _ = self.principal_eigen()  
            self._cache_lambda_max = float(lam)
        return self._cache_lambda_max

    @property
    def ci(self) -> float:  
        if self._cache_ci is None:
            n = self.matrix.shape[0]  
            self._cache_ci = float((self.lambda_max - n) / (n - 1)) if n > 1 else 0.0
        return self._cache_ci

    @property
    def cr(self) -> float:  
        if self._cache_cr is None:
            n = self.matrix.shape[0]  
            ri = _RI.get(n, _RI[max(_RI.keys())])
            self._cache_cr = float(self.ci / ri) if ri > 0 else 0.0
        return self._cache_cr


@dataclass(slots=True)
class PairwiseComparison(ConsistencyMixin):
    """Pairwise comparison matrix (square, positive, reciprocal, 1.0 diag)."""

    labels: List[Label]
    matrix: FloatArray
    _cache_evec: Optional[FloatArray] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        n = len(self.labels)
        if self.matrix.shape != (n, n):
            raise ValueError("Matrix shape must match labels length")
        if not np.all(self.matrix > 0):
            raise ValueError("All comparison values must be positive")
        if not np.allclose(np.diag(self.matrix), 1.0):
            raise ValueError("Diagonal must be 1.0")
        if not np.allclose(self.matrix * self.matrix.T, 1.0, atol=1e-6):
            raise ValueError("Matrix must be reciprocal: a_ij * a_ji = 1")

    @classmethod
    def from_judgments(
        cls, labels: Iterable[Label], judgments: Judgment
    ) -> "PairwiseComparison":
        """Build from sparse judgments; (i,j): i is x times preferred to j."""
        labels_list = list(labels)
        n = len(labels_list)
        idx = {name: k for k, name in enumerate(labels_list)}
        M: FloatArray = np.ones((n, n), dtype=np.float64)
        for (i, j), val in judgments.items():
            if i not in idx or j not in idx:
                raise KeyError(f"Unknown label in judgment: ({i}, {j})")
            if not SaatyScale.is_valid(val):
                raise ValueError(f"Invalid ratio for ({i}, {j}): {val}")
            a, b = idx[i], idx[j]
            v = float(val)
            M[a, b] = v
            M[b, a] = 1.0 / v
        return cls(labels=labels_list, matrix=M)

    def principal_eigen(self) -> tuple[float, FloatArray]:
        if self._cache_evec is not None and self._cache_lambda_max is not None:
            return self._cache_lambda_max, self._cache_evec  # type: ignore[return-value]
        vals, vecs = np.linalg.eig(self.matrix)
        i = int(np.argmax(np.real(vals)))
        lam = float(np.real(vals[i]))
        v = np.real(vecs[:, i])
        v = np.abs(v)
        v = v / v.sum()
        self._cache_lambda_max = lam
        self._cache_evec = v.astype(np.float64)
        self._cache_ci = None
        self._cache_cr = None
        return self._cache_lambda_max, self._cache_evec

    def priorities(self) -> FloatArray:
        return self.principal_eigen()[1]

    def consistency_ratio(self) -> tuple[float, float, float]:
        return float(self.cr), float(self.ci), float(self.lambda_max)
