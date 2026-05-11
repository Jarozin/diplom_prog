from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Mapping, Iterable, overload, Any, Self

from typing import cast
from saatypy.components.types import (
    AHPReportData,
    AHPInputs,
    AHPInputsCriteria,
)


import numpy as np
from saatypy.decision_model import DecisionModel
from saatypy.components.types import Label, FloatArray
from saatypy.components.pairwise import PairwiseComparison
from saatypy.components.math import normalize_vector_nonneg, aligned_vector_from_mapping

__all__ = ["AHPModel", "AHPBuilder"]


@dataclass(slots=True)
class AHPModel(DecisionModel):
    """
    Classic AHP with optional hierarchical criteria (groups -> subcriteria).

    Exposes `to_report_data()` including inputs (judgments) when PCs are provided.
    """

    criteria: List[Label]
    alternatives: List[Label]
    criteria_groups: Optional[Dict[Label, List[Label]]] = None

    _criteria_weights: Optional[Dict[Label, float]] = None
    _group_weights: Optional[Dict[Label, float]] = None
    _subcriteria_weights: Optional[Dict[Label, Dict[Label, float]]] = None
    _alt_local: Dict[Label, FloatArray] = field(default_factory=dict)

    _criteria_pc: Optional[PairwiseComparison] = None
    _alt_pcs: Dict[Label, PairwiseComparison] = field(default_factory=dict)

    def _labels_check(
        self, labels: Iterable[Label], domain: Iterable[Label], kind: str
    ) -> None:
        L, D = set(labels), set(domain)
        if L != D:
            missing = D - L
            extra = L - D
            raise ValueError(
                f"{kind} labels mismatch. Missing={missing}, Extra={extra}"
            )

    def _normalize_vec(
        self, values: Mapping[Label, float], order: List[Label]
    ) -> Dict[Label, float]:
        vec = aligned_vector_from_mapping(order, values)
        return {n: float(v) for n, v in zip(order, vec)}

    @overload
    def set_criteria_weights(self, weights: Mapping[Label, float]) -> None: ...
    @overload
    def set_criteria_weights(self, weights: FloatArray) -> None: ...
    @overload
    def set_criteria_weights(self, weights: PairwiseComparison) -> None: ...
    def set_criteria_weights(self, weights) -> None:
        """Set flat criteria weights from dict/array/PC; stores PC (if provided)."""
        if self.criteria_groups is not None:
            raise ValueError(
                "Groups defined; use set_group_weights + set_subcriteria_weights"
            )
        names = list(self.criteria)
        if isinstance(weights, PairwiseComparison):
            self._labels_check(weights.labels, names, "Criteria PC")
            vec = np.array(
                [weights.priorities()[weights.labels.index(n)] for n in names],
                dtype=np.float64,
            )
            self._criteria_weights = {
                n: float(v) for n, v in zip(names, normalize_vector_nonneg(vec))
            }
            self._criteria_pc = weights
        elif hasattr(weights, "ndim"):
            arr = np.asarray(weights, dtype=np.float64)
            if arr.ndim != 1 or arr.size != len(names):
                raise ValueError("Criteria array shape mismatch")
            self._criteria_weights = self._normalize_vec(
                dict(zip(names, arr.tolist())), names
            )
            self._criteria_pc = None
        else:
            self._criteria_weights = self._normalize_vec(weights, names)
            self._criteria_pc = None

    @overload
    def set_group_weights(self, weights: Mapping[Label, float]) -> None: ...
    @overload
    def set_group_weights(self, weights: FloatArray) -> None: ...
    @overload
    def set_group_weights(self, weights: PairwiseComparison) -> None: ...
    def set_group_weights(self, weights) -> None:
        if not self.criteria_groups:
            raise ValueError("No groups defined; use criteria_groups(...) in builder.")
        groups = list(self.criteria_groups.keys())
        if isinstance(weights, PairwiseComparison):
            self._labels_check(weights.labels, groups, "Group PC")
            vec = np.array(
                [weights.priorities()[weights.labels.index(n)] for n in groups],
                dtype=np.float64,
            )
            self._group_weights = {
                n: float(v) for n, v in zip(groups, normalize_vector_nonneg(vec))
            }
        elif hasattr(weights, "ndim"):
            arr = np.asarray(weights, dtype=np.float64)
            if arr.ndim != 1 or arr.size != len(groups):
                raise ValueError("Group array shape mismatch")
            self._group_weights = self._normalize_vec(
                dict(zip(groups, arr.tolist())), groups
            )
        else:
            self._group_weights = self._normalize_vec(weights, groups)

    @overload
    def set_subcriteria_weights(
        self, group: Label, weights: Mapping[Label, float]
    ) -> None: ...
    @overload
    def set_subcriteria_weights(self, group: Label, weights: FloatArray) -> None: ...
    @overload
    def set_subcriteria_weights(
        self, group: Label, weights: PairwiseComparison
    ) -> None: ...
    def set_subcriteria_weights(self, group: Label, weights) -> None:
        if not self.criteria_groups:
            raise ValueError("No groups defined.")
        if group not in self.criteria_groups:
            raise KeyError(f"Unknown group '{group}'")
        subs = list(self.criteria_groups[group])
        if isinstance(weights, PairwiseComparison):
            self._labels_check(weights.labels, subs, f"Subcriteria PC for '{group}'")
            vec = np.array(
                [weights.priorities()[weights.labels.index(n)] for n in subs],
                dtype=np.float64,
            )
            self._subcriteria_weights = self._subcriteria_weights or {}
            self._subcriteria_weights[group] = {
                n: float(v) for n, v in zip(subs, normalize_vector_nonneg(vec))
            }
        elif hasattr(weights, "ndim"):
            arr = np.asarray(weights, dtype=np.float64)
            if arr.ndim != 1 or arr.size != len(subs):
                raise ValueError("Subcriteria array shape mismatch")
            self._subcriteria_weights = self._subcriteria_weights or {}
            self._subcriteria_weights[group] = self._normalize_vec(
                dict(zip(subs, arr.tolist())), subs
            )
        else:
            self._subcriteria_weights = self._subcriteria_weights or {}
            self._subcriteria_weights[group] = self._normalize_vec(weights, subs)

    @overload
    def set_alt_priorities(
        self, criterion: Label, pc_or_judgments: PairwiseComparison
    ) -> None: ...
    @overload
    def set_alt_priorities(
        self, criterion: Label, pc_or_judgments: Mapping[Tuple[Label, Label], float]
    ) -> None: ...
    @overload
    def set_alt_priorities(
        self, criterion: Label, pc_or_judgments: FloatArray
    ) -> None: ...
    def set_alt_priorities(self, criterion: Label, pc_or_judgments) -> None:
        """Record local priorities from PC / judgments / vector; store PC when available."""
        # Validate criterion exists
        if criterion not in self.criteria:
            raise KeyError(f"Unknown criterion '{criterion}'")
            
        names = list(self.alternatives)
        if isinstance(pc_or_judgments, PairwiseComparison):
            self._labels_check(
                pc_or_judgments.labels, names, f"Alt PC for '{criterion}'"
            )
            vec = np.array(
                [
                    pc_or_judgments.priorities()[pc_or_judgments.labels.index(n)]
                    for n in names
                ],
                dtype=np.float64,
            )
            self._alt_local[criterion] = normalize_vector_nonneg(vec)
            self._alt_pcs[criterion] = pc_or_judgments
            return
        if hasattr(pc_or_judgments, "ndim"):
            arr = np.asarray(pc_or_judgments, dtype=np.float64)
            if arr.ndim != 1 or arr.size != len(names):
                raise ValueError("Alternative priority vector shape mismatch")
            self._alt_local[criterion] = normalize_vector_nonneg(arr)
            return
        pc = PairwiseComparison.from_judgments(labels=names, judgments=pc_or_judgments)
        vec = pc.priorities().astype(np.float64)
        self._alt_local[criterion] = normalize_vector_nonneg(vec)
        self._alt_pcs[criterion] = pc

    def _flat_criteria_weights(self) -> Dict[Label, float]:
        if not self.criteria_groups:
            if not self._criteria_weights:
                raise ValueError(
                    "Criteria weights are not set. Call set_criteria_weights()."
                )
            return dict(self._criteria_weights)
        if not self._group_weights:
            raise ValueError("Group weights are not set. Call set_group_weights().")
        if not self._subcriteria_weights:
            raise ValueError("Subcriteria weights are not fully set.")
        flat: Dict[Label, float] = {}
        for g, subs in self.criteria_groups.items():
            gw = self._group_weights.get(g)
            if gw is None:
                raise ValueError(f"Missing group weight for '{g}'")
            sws = self._subcriteria_weights.get(g)
            if sws is None or set(sws.keys()) != set(subs):
                raise ValueError(
                    f"Subcriteria weights missing/mismatch for group '{g}'"
                )
            for s in subs:
                flat[s] = float(gw) * float(sws[s])
        vec = np.array(list(flat.values()), dtype=np.float64)
        vec = normalize_vector_nonneg(vec)
        return {k: float(v) for k, v in zip(flat.keys(), vec)}

    def alternative_priorities(self) -> Tuple[FloatArray, List[Label]]:
        """Return normalized global priorities and alternative names."""
        crit_weights = self._flat_criteria_weights()
        missing = [c for c in crit_weights.keys() if c not in self._alt_local]
        if missing:
            raise ValueError(f"Missing alternative priorities for criteria: {missing}")
        names = list(self.alternatives)
        A = np.zeros(len(names), dtype=np.float64)
        for c, w in crit_weights.items():
            A += float(w) * self._alt_local[c]
        A = normalize_vector_nonneg(A)
        return A.astype(np.float64), names

    def _pc_to_judgments(self, pc: PairwiseComparison) -> List[Dict[str, float | str]]:
        """Serialize upper-triangle judgments as [{'i','j','value'}, ...]."""
        labels = pc.labels
        M = pc.matrix
        out: List[Dict[str, float | str]] = []
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                out.append({"i": labels[i], "j": labels[j], "value": float(M[i, j])})
        return out

    def to_report_data(self) -> AHPReportData:
        """Return a typed dict for adapters + renderers (includes inputs if available)."""
        crit = dict(self._flat_criteria_weights())
        alt_vec, alt_names = self.alternative_priorities()
        ranking = sorted(
            zip(alt_names, alt_vec.tolist()), key=lambda x: x[1], reverse=True
        )

        cons_norm: Dict[str, Any] = {}
        inputs: AHPInputs = {
            "criteria": cast(AHPInputsCriteria, {}),
            "alternatives": {},
        }
        if self._criteria_pc is not None:
            inputs["criteria"]["judgments"] = self._pc_to_judgments(self._criteria_pc)
        for c, pc in self._alt_pcs.items():
            inputs["alternatives"][c] = self._pc_to_judgments(pc)

        return {
            "criteria_weights": {k: float(v) for k, v in crit.items()},
            "local_alternatives": {
                c: v.astype(float).tolist() for c, v in self._alt_local.items()
            },
            "alternatives": alt_names,
            "global_priorities": [float(x) for x in alt_vec],
            "ranking_str": " > ".join([n for n, _ in ranking]),
            "consistency": cast(dict, cons_norm),  # narrow later to AHPConsistencyData
            "inputs": inputs,
        }


class AHPBuilder:
    """Ergonomic helper to build a model without repeating labels."""

    def __init__(self) -> None:
        self._criteria: Optional[List[Label]] = None
        self._criteria_groups: Optional[Dict[Label, List[Label]]] = None
        self._alternatives: Optional[List[Label]] = None

    def add_criteria(self, names: Iterable[Label]) -> Self:
        L = list(names)
        if len(set(L)) != len(L):
            raise ValueError("Duplicate criteria")
        self._criteria = L
        self._criteria_groups = None
        return self

    def add_criteria_groups(self, groups: Mapping[Label, Iterable[Label]]) -> Self:
        gdict = {g: list(subs) for g, subs in groups.items()}
        all_subs = [s for subs in gdict.values() for s in subs]
        if len(set(all_subs)) != len(all_subs):
            raise ValueError("Duplicate subcriteria across groups")
        self._criteria = all_subs
        self._criteria_groups = {g: list(subs) for g, subs in gdict.items()}
        return self

    def add_alternatives(self, names: Iterable[Label]) -> Self:
        L = list(names)
        if len(set(L)) != len(L):
            raise ValueError("Duplicate alternatives")
        self._alternatives = L
        return self

    def build(self) -> AHPModel:
        if not self._alternatives:
            raise ValueError("Define alternatives via .add_alternatives(...)")
        if not self._criteria:
            raise ValueError(
                "Define criteria via .add_criteria(...) or .add_criteria_groups(...)"
            )
        return AHPModel(
            criteria=self._criteria,
            alternatives=self._alternatives,
            criteria_groups=self._criteria_groups,
        )
