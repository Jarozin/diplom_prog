from __future__ import annotations

from typing import Mapping, Tuple, TypeAlias
import numpy as np
from numpy.typing import NDArray


from typing import Dict, List, TypedDict, Literal, Union

Label: TypeAlias = str
Judgment: TypeAlias = Mapping[Tuple[Label, Label], float]
FloatArray: TypeAlias = NDArray[np.float64]



class JudgmentEntry(TypedDict):
    """Serialized pairwise judgment for (i,j) with ratio value."""

    i: str
    j: str
    value: float




class AHPInputsCriteria(TypedDict, total=False):
    """Optional inputs for criteria level."""

    judgments: List[JudgmentEntry]  # present if criteria PC was supplied


class AHPInputs(TypedDict):
    """All input judgments included in the report."""

    criteria: AHPInputsCriteria
    alternatives: Dict[str, List[JudgmentEntry]]


class AHPConsistencyData(TypedDict, total=False):
    """Optional consistency section."""

    criteria: float
    alternatives: Dict[str, float]


class AHPReportData(TypedDict):
    """Structured AHP report dictionary returned by AHPModel.to_report_data()."""

    criteria_weights: Dict[str, float]
    local_alternatives: Dict[str, List[float]]
    alternatives: List[str]
    global_priorities: List[float]
    ranking_str: str
    consistency: AHPConsistencyData
    inputs: AHPInputs




class DenseBlockMeta(TypedDict):
    """Metadata when a block was given as a dense matrix."""

    type: Literal["dense"]
    shape: Tuple[int, int]


class PCMapBlockMeta(TypedDict):
    """Metadata when a block was built from PCs / judgments per source node."""

    type: Literal["pc_map"]
    shape: Tuple[int, int]
    entries: Dict[str, List[JudgmentEntry]]


BlockMeta = Union[DenseBlockMeta, PCMapBlockMeta]


class ANPConsistencyData(TypedDict, total=False):
    """Optional ANP consistency metrics (extend as you add CRs)."""

    clusters: float
    blocks: Dict[str, float]


class ANPReportData(TypedDict):
    """Structured ANP report dictionary returned by ANPModel.to_report_data()."""

    cluster_weights: Dict[str, float]
    max_col_deviation: float
    alternatives: List[str]
    global_priorities: List[float]
    ranking_str: str
    consistency: ANPConsistencyData
    blocks: Dict[str, BlockMeta]
