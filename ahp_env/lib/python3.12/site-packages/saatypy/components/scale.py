from __future__ import annotations
from typing import Final, Dict


class SaatyScale:
    """
    Saaty 1–9 scale helper.
    NOTE: We allow any positive ratio (>0) to support continuous judgments.
    """

    ALLOWED: Final[tuple[float, ...]] = (1, 2, 3, 4, 5, 6, 7, 8, 9)

    @staticmethod
    def reciprocal(x: float) -> float:
        if x <= 0:
            raise ValueError("Saaty intensity must be > 0")
        return 1.0 / x

    @staticmethod
    def is_valid(x: float) -> bool:
        return x > 0


# Random Index (RI) values for CR computation (Saaty, n=1..15). We cap at 15.
_RI: Final[Dict[int, float]] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.48,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}
RI_TABLE: Final[Dict[int, float]] = _RI
