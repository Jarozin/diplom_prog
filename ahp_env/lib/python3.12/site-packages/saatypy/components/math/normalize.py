from __future__ import annotations
from typing import Mapping, List
import numpy as np
from saatypy.components.types import Label, FloatArray
from saatypy.components.errors import NormalizationError


def normalize_vector_nonneg(vec: FloatArray) -> FloatArray:
    """Normalize a non-negative vector to sum to 1.0."""
    if np.any(vec < 0):
        raise NormalizationError("Weights must be non-negative")
    s = float(vec.sum())
    if s <= 0:
        raise NormalizationError("Weights must sum to a positive number")
    return (vec / s).astype(np.float64)


def normalize_columns_inplace(M: FloatArray) -> None:
    """Normalize columns to sum to 1 where the column sum is positive."""
    for c in range(M.shape[1]):
        s = float(M[:, c].sum())
        if s > 0:
            M[:, c] /= s


def aligned_vector_from_mapping(
    order: List[Label], values: Mapping[Label, float]
) -> FloatArray:
    """Create a vector aligned with `order` from a {label: weight} mapping and normalize."""
    missing = set(order) - set(values.keys())
    extra = set(values.keys()) - set(order)
    if missing or extra:
        raise NormalizationError(f"Labels mismatch. Missing={missing}, Extra={extra}")
    arr = np.array([float(values[n]) for n in order], dtype=np.float64)
    return normalize_vector_nonneg(arr)
