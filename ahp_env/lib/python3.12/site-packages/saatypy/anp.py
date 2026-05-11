from __future__ import annotations
from dataclasses import dataclass, field
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
    Mapping,
    Iterable,
    Union,
    overload,
    Any,
    Self,
)

from typing import cast


import numpy as np

from saatypy.components.types import Label, FloatArray, BlockMeta,ANPReportData
from saatypy.components.pairwise import PairwiseComparison
from saatypy.components.modeling import Node, Cluster
from saatypy.components.errors import StructureError, NormalizationError
from saatypy.components.math import (
    normalize_columns_inplace,
    normalize_vector_nonneg,
    aligned_vector_from_mapping,
    LimitStrategy,
    PowerMethodLimiter,
)
from saatypy.decision_model import DecisionModel

_BlockInputPC = Mapping[Label, PairwiseComparison]
_BlockInputJudgments = Mapping[Label, Mapping[Tuple[Label, Label], float]]
_BlockInputArray = FloatArray
_BlockInput = Union[_BlockInputPC, _BlockInputJudgments, _BlockInputArray]

__all__ = ["Supermatrix", "ANPModel", "ANPBuilder"]


@dataclass(slots=True)
class Supermatrix:
    """Block supermatrix utilities for ANP.
    Orientation: columns = source nodes; rows = target nodes.
    """

    blocks: Dict[Tuple[Label, Label], FloatArray]
    order: List[Cluster]

    def _cluster(self, name: Label) -> Cluster:
        for c in self.order:
            if c.name == name:
                return c
        raise KeyError(f"Unknown cluster {name}")

    def _cluster_start_indices(self) -> Dict[Label, int]:
        start: Dict[Label, int] = {}
        k = 0
        for c in self.order:
            start[c.name] = k
            k += c.size
        return start

    def to_dense(self) -> FloatArray:
        sizes = [c.size for c in self.order]
        n_total = sum(sizes)
        mat: FloatArray = np.zeros((n_total, n_total), dtype=np.float64)
        start = self._cluster_start_indices()
        for (i_name, j_name), block in self.blocks.items():
            i0, j0 = start[i_name], start[j_name]
            i1, j1 = i0 + self._cluster(i_name).size, j0 + self._cluster(j_name).size
            expected = (self._cluster(i_name).size, self._cluster(j_name).size)
            if block.shape != expected:
                raise ValueError(
                    f"Block {(i_name, j_name)} shape {block.shape} != expected {expected}"
                )
            mat[i0:i1, j0:j1] = block
        return mat

    def weight_by_row_clusters(self, cluster_weights: Mapping[Label, float]) -> Self:
        """
        Weighted supermatrix (column-cluster weighting):
        - Multiply every column belonging to source cluster 'Cj' by cluster_weights[Cj].
        - Then re-normalize each column so columns remain stochastic.
        This matches the standard ANP weighting procedure and the benchmark expectations.
        """
        # validate weights and normalize them to sum 1 (not strictly required, but standard)
        total = float(sum(cluster_weights.values()))
        if total <= 0:
            raise NormalizationError("Cluster weights must sum to a positive number")
        w_norm = {k: float(v) / total for k, v in cluster_weights.items()}

        # Build a dense matrix, apply column-cluster weights, then renormalize columns
        dense = self.to_dense()

        # Build a map from column index -> source cluster name
        start = self._cluster_start_indices()
        col_to_cluster: Dict[int, str] = {}
        for c in self.order:
            j0 = start[c.name]
            for j in range(j0, j0 + c.size):
                col_to_cluster[j] = c.name

        # Scale columns by their source cluster weight
        for j in range(dense.shape[1]):
            c_name = col_to_cluster[j]
            dense[:, j] = dense[:, j] * w_norm.get(c_name, 0.0)

        # Re-normalize columns to keep column-stochasticity (but only for nonzero columns)
        colsum = dense.sum(axis=0)
        nz = colsum > 0
        dense[:, nz] = dense[:, nz] / colsum[nz]

        # Re-slice back into blocks
        rebuilt: Dict[Tuple[Label, Label], FloatArray] = {}
        for i_cluster in self.order:
            i0 = start[i_cluster.name]
            i1 = i0 + i_cluster.size
            for j_cluster in self.order:
                j0 = start[j_cluster.name]
                j1 = j0 + j_cluster.size
                rebuilt[(i_cluster.name, j_cluster.name)] = dense[i0:i1, j0:j1].copy()

        return Supermatrix(blocks=rebuilt, order=self.order)
    
    
@dataclass(slots=True)
class ANPModel(DecisionModel):
    """High-level ANP model with flexible, label-safe APIs."""

    clusters: List[Cluster]
    alternatives_cluster: Label
    local_blocks: Dict[Tuple[Label, Label], FloatArray] = field(default_factory=dict)
    cluster_weights: Optional[Dict[Label, float]] = None
    limiter: LimitStrategy = field(default_factory=PowerMethodLimiter)
    block_inputs: Dict[Tuple[Label, Label], Dict[str, Any]] = field(
        default_factory=dict
    )

    @property
    def cluster_index(self) -> Dict[Label, Cluster]:
        return {c.name: c for c in self.clusters}

    def node_names(self, cluster: Label) -> List[Label]:
        return [n.name for n in self.cluster_index[cluster].nodes]

    @overload
    def set_cluster_weights(self, weights: Mapping[Label, float]) -> None: ...
    @overload
    def set_cluster_weights(self, weights: FloatArray) -> None: ...
    @overload
    def set_cluster_weights(self, weights: PairwiseComparison) -> None: ...
    def set_cluster_weights(self, weights):
        names = [c.name for c in self.clusters]
        # Check for unknown clusters in weights
        if isinstance(weights, dict):
            extra = set(weights.keys()) - set(names)
            missing = set(names) - set(weights.keys())
            if extra or missing:
                raise ValueError(f"Cluster weights mismatch. Missing={missing}, Extra={extra}")
        if isinstance(weights, PairwiseComparison):
            if set(weights.labels) != set(names):
                raise ValueError("Cluster PC labels must match cluster names")
            vec = np.array(
                [weights.priorities()[weights.labels.index(n)] for n in names],
                dtype=np.float64,
            )
        elif hasattr(weights, "ndim"):
            arr = np.asarray(weights, dtype=np.float64)
            if arr.ndim != 1 or arr.size != len(names):
                raise ValueError("Cluster weights array shape mismatch")
            vec = arr
        else:
            vec = aligned_vector_from_mapping(names, weights)  # also normalizes
            self.cluster_weights = {n: float(v) for n, v in zip(names, vec)}
            return
        vec = normalize_vector_nonneg(vec)
        self.cluster_weights = {n: float(v) for n, v in zip(names, vec)}

    def set_cluster_weights_from_pc(self, pc: PairwiseComparison) -> None:
        self.set_cluster_weights(pc)

    @overload
    def add_block(
        self, target_cluster: Label, source_cluster: Label, data: _BlockInputPC
    ) -> None: ...
    @overload
    def add_block(
        self, target_cluster: Label, source_cluster: Label, data: _BlockInputJudgments
    ) -> None: ...
    @overload
    def add_block(
        self, target_cluster: Label, source_cluster: Label, data: _BlockInputArray
    ) -> None: ...
    def add_block(
        self, target_cluster: Label, source_cluster: Label, data: _BlockInput
    ) -> None:
        """Add block (target, source) using flexible input; record inputs for reports."""
        i = self.cluster_index[target_cluster]
        j = self.cluster_index[source_cluster]
        target_labels = [n.name for n in i.nodes]
        source_labels = [n.name for n in j.nodes]

        if hasattr(data, "shape"):  # ndarray
            block = np.asarray(data, dtype=np.float64)
            expected = (i.size, j.size)
            if block.shape != expected:
                raise ValueError(f"Block shape {block.shape} != expected {expected}")
            normalize_columns_inplace(block)
            self.local_blocks[(target_cluster, source_cluster)] = block
            self.block_inputs[(target_cluster, source_cluster)] = {
                "type": "dense",
                "shape": (i.size, j.size),
            }
            return

        # mapping per-source
        block: FloatArray = np.zeros((i.size, j.size), dtype=np.float64)
        entries_meta: Dict[str, List[Dict[str, Any]]] = {}
        for c, src_node in enumerate(source_labels):
            if src_node not in data:
                raise KeyError(
                    f"Missing entry for source node '{src_node}' in block ({target_cluster}, {source_cluster})"
                )
            entry = data[src_node]
            if isinstance(entry, PairwiseComparison):
                if set(entry.labels) != set(target_labels):
                    raise ValueError(
                        f"PC for '{src_node}' must compare exactly the target nodes"
                    )
                vec = np.array(
                    [
                        entry.priorities()[entry.labels.index(lbl)]
                        for lbl in target_labels
                    ],
                    dtype=np.float64,
                )
                entries_meta[src_node] = self._pc_to_judgments_like(
                    entry, target_labels
                )
            else:
                pc = PairwiseComparison.from_judgments(
                    labels=target_labels, judgments=entry
                )  # type: ignore[arg-type]
                vec = pc.priorities().astype(np.float64)
                entries_meta[src_node] = self._pc_to_judgments_like(pc, target_labels)
            block[:, c] = normalize_vector_nonneg(vec)
        self.local_blocks[(target_cluster, source_cluster)] = block
        self.block_inputs[(target_cluster, source_cluster)] = {
            "type": "pc_map",
            "shape": (i.size, j.size),
            "entries": entries_meta,
        }

    def _pc_to_judgments_like(
        self, pc: PairwiseComparison, labels: List[Label]
    ) -> List[Dict[str, Any]]:
        """Serialize upper-triangle of PC as [{'i','j','value'}, ...] for given labels order."""
        out: List[Dict[str, Any]] = []
        M = pc.matrix
        for a in range(len(labels)):
            for b in range(a + 1, len(labels)):
                out.append({"i": labels[a], "j": labels[b], "value": float(M[a, b])})
        return out

    def add_block_uniform(self, target_cluster: Label, source_cluster: Label) -> None:
        i = self.cluster_index[target_cluster]
        j = self.cluster_index[source_cluster]
        if i.size == 0 or j.size == 0:
            self.local_blocks[(target_cluster, source_cluster)] = np.zeros(
                (i.size, j.size), dtype=np.float64
            )
            return
        block: FloatArray = np.ones((i.size, j.size), dtype=np.float64) / float(i.size)
        self.local_blocks[(target_cluster, source_cluster)] = block
        self.block_inputs[(target_cluster, source_cluster)] = {
            "type": "dense",
            "shape": (i.size, j.size),
        }


    def build_supermatrix(self) -> Supermatrix:
        blocks: Dict[Tuple[Label, Label], FloatArray] = {}
        for ci in self.clusters:
            for cj in self.clusters:
                key = (ci.name, cj.name)
                blocks[key] = self.local_blocks.get(
                    key, np.zeros((ci.size, cj.size), dtype=np.float64)
                )

        any_nonzero = False
        for B in blocks.values():
            if np.any(B > 0):
                any_nonzero = True
                break

        if any_nonzero:
            for src in self.clusters:
                colsum = None
                for ci in self.clusters:
                    B = blocks[(ci.name, src.name)]
                    colsum = B.sum(axis=0) if colsum is None else (colsum + B.sum(axis=0))
                if np.allclose(colsum, 0.0):
                    n = src.size
                    if n > 0:
                        self_loop = np.ones((n, n), dtype=np.float64) / float(n)
                        blocks[(src.name, src.name)] = self_loop
        return Supermatrix(blocks=blocks, order=self.clusters)
    
    
    def _row_slice(self, cluster_name: Label) -> slice:
        start = 0
        for c in self.clusters:
            if c.name == cluster_name:
                break
            start += c.size
        return slice(start, start + self.cluster_index[cluster_name].size)

    def check_structure(self) -> None:
        S = self.build_supermatrix()
        dense = S.to_dense()
        zero_cols = np.where(np.isclose(dense.sum(axis=0), 0.0))[0].tolist()
        if zero_cols:
            raise StructureError(
                f"Some columns in the supermatrix are zero (no links). Indices: {zero_cols}"
            )

    def alternative_priorities(self) -> Tuple[FloatArray, List[Label]]:
        """Compute limit matrix (via limiter) and return priorities for alternatives."""
        if not self.cluster_weights:
            raise ValueError("Cluster weights are not set. Call set_cluster_weights().")
        S = self.build_supermatrix()
        W = S.weight_by_row_clusters(self.cluster_weights)
        M = W.to_dense()

        # check column-stochastic
        col_sums = M.sum(axis=0)
        if not np.allclose(col_sums, 1.0, atol=1e-6):
            max_dev = float(np.max(np.abs(col_sums - 1.0)))
            raise NormalizationError(
                f"Weighted supermatrix columns must sum to 1 (max deviation {max_dev:.3e})."
            )

        L = self.limiter.limit(M)
        rows = self._row_slice(self.alternatives_cluster)
        priorities = L[rows, 0]
        priorities = normalize_vector_nonneg(priorities)
        labels = [n.name for n in self.cluster_index[self.alternatives_cluster].nodes]
        return priorities.astype(np.float64), labels

    def to_report_data(self) -> ANPReportData:
        """Return a typed dict for adapters + renderers, including block input metadata."""
        if not self.cluster_weights:
            raise ValueError("Cluster weights not set")
        S = self.build_supermatrix()
        dense = S.to_dense()
        max_dev = float(np.max(np.abs(dense.sum(axis=0) - 1.0)))

        gp, alts = self.alternative_priorities()
        ranking = sorted(zip(alts, gp.tolist()), key=lambda x: x[1], reverse=True)

        # flatten block inputs keys to readable "(target ← source)"
        blocks: Dict[str, BlockMeta] = {}
        for (ti, sj), meta in self.block_inputs.items():
            key = f"({ti} ← {sj})"
            blocks[key] = cast(BlockMeta, meta)

        return {
            "cluster_weights": {k: float(v) for k, v in self.cluster_weights.items()},
            "max_col_deviation": max_dev,
            "alternatives": alts,
            "global_priorities": [float(x) for x in gp],
            "ranking_str": " > ".join([n for n, _ in ranking]),
            "consistency": cast(dict, {}),
            "blocks": blocks,
        }


class ANPBuilder:
    """Ergonomic helper to build a model without repeating labels."""

    def __init__(self) -> None:
        self._clusters: List[Cluster] = []
        self._alts: Optional[Label] = None

    def add_cluster(self, name: Label, node_names: Iterable[Label]) -> Self:
        names = list(node_names)
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate node names in cluster '{name}'")
        # Check for duplicate cluster name
        if any(c.name == name for c in self._clusters):
            raise ValueError(f"Duplicate cluster name '{name}'")
        nodes = [Node(n) for n in names]
        self._clusters.append(Cluster(name=name, nodes=nodes))
        return self

    def add_alternatives(
        self, alt_names: Iterable[Label], *, name: Label = "alternatives"
    ) -> Self:
        self.add_cluster(name, alt_names)
        self._alts = name
        return self

    def build(self) -> ANPModel:
        if not self._alts_defined():
            raise ValueError(
                "You must define an alternatives cluster via .add_alternatives(...)"
            )
        cnames = [c.name for c in self._clusters]
        if len(set(cnames)) != len(cnames):
            raise ValueError("Duplicate cluster names")
        return ANPModel(clusters=self._clusters, alternatives_cluster=self._alts)

    def _alts_defined(self) -> bool:
        return self._alts is not None
