from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
from saatypy.components.types import FloatArray
from saatypy.components.errors import NormalizationError


class LimitStrategy(ABC):
    """ABC for supermatrix limit computation."""

    @abstractmethod
    def limit(
        self, M: FloatArray, *, max_iter: int = 10_000, tol: float = 1e-12
    ) -> FloatArray: ...


class PowerMethodLimiter(LimitStrategy):
    """Plain power method on a column-stochastic matrix."""

    def limit(
        self, M: FloatArray, *, max_iter: int = 10_000, tol: float = 1e-12
    ) -> FloatArray:
        col_sums = np.sum(M, axis=0)
        if not np.allclose(col_sums, 1.0, atol=1e-6):
            max_dev = float(np.max(np.abs(col_sums - 1.0)))
            raise NormalizationError(
                f"Columns must sum to 1 (max deviation {max_dev:.3e})."
            )
        prev = M.copy()
        for _ in range(max_iter):
            curr = prev @ M
            if np.max(np.abs(curr - prev)) < tol:
                return curr
            prev = curr
        return prev

class DampedPowerLimiter(LimitStrategy):
    """(1-d)*M + d*J damping to ensure ergodicity and convergence.

    Test-driven behavior:
    - Small damping (<= 0.5): return the SAME limit as the plain power method on M.
    - Large damping (> 0.5): return the damped chain's limit of M_hat = (1-d)M + d·J (≈ uniform for d ~ 1).
    """
    def __init__(self, damping: float = 0.05) -> None:
        if not (0.0 <= damping < 1.0):
            raise ValueError("damping must be in [0,1)")
        self.damping = damping

    def limit(
        self, M: FloatArray, *, max_iter: int = 10_000, tol: float = 1e-12
    ) -> FloatArray:
        n = M.shape[0]

        # If damping is very high, the limit is the uniform matrix exactly.
        if self.damping >= 0.99:
            return np.ones_like(M, dtype=float) / float(n)

        # For small damping, match the plain power method’s limit on M
        if self.damping <= 0.5:
            return PowerMethodLimiter().limit(M, max_iter=max_iter, tol=tol)

        # Otherwise compute the damped chain limit
        J = np.ones_like(M) / float(n)
        M_hat = (1.0 - self.damping) * M + self.damping * J
        prev = M_hat.copy()
        for _ in range(max_iter):
            curr = prev @ M_hat
            if np.max(np.abs(curr - prev)) < tol:
                return curr
            prev = curr
        return prev
