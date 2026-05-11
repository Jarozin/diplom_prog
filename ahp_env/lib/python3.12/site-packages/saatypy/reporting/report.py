from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from saatypy.ahp import AHPModel
from saatypy.anp import ANPModel
from saatypy.utils.common import atomic_write, fmt_table, Row, Header


@dataclass(frozen=True)
class TableData:
    """Two-column table data; a good fit for vectors and judgment pairs."""

    header: Header
    rows: List[Row] = field(default_factory=list)


@dataclass(frozen=True)
class Section:
    """A section contains free paragraphs and any number of two-column tables."""

    title: str
    paragraphs: List[str] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)


@dataclass(frozen=True)
class GenericReport:
    """Renderer-agnostic, minimal document tree."""

    title: str
    sections: List[Section] = field(default_factory=list)


class Renderer(ABC):
    """ABC for rendering a GenericReport to text."""

    @abstractmethod
    def heading(self, text: str, level: int = 2) -> str: ...
    @abstractmethod
    def paragraph(self, text: str) -> str: ...
    @abstractmethod
    def table(self, table: TableData) -> str: ...
    @abstractmethod
    def join(self, parts: Iterable[str]) -> str: ...

    def render(self, report: GenericReport) -> str:
        """Default rendering pipeline shared by all renderers."""
        parts: List[str] = [self.heading(report.title, level=2)]
        for sec in report.sections:
            parts.append(self.heading(sec.title, level=3))
            for p in sec.paragraphs:
                parts.append(self.paragraph(p))
            for t in sec.tables:
                parts.append(self.table(t))
        return self.join(parts)


class MarkdownRenderer(Renderer):
    """Markdown renderer ('.md')."""

    def heading(self, text: str, level: int = 2) -> str:
        return f"{'#' * level} {text}\n\n"

    def paragraph(self, text: str) -> str:
        return text.rstrip() + "\n\n"

    def table(self, table: TableData) -> str:
        return fmt_table(table.rows, table.header, markdown=True)

    def join(self, parts: Iterable[str]) -> str:
        return "".join(parts)


class PlainRenderer(Renderer):
    """Plain text renderer ('.txt')."""

    def heading(self, text: str, level: int = 2) -> str:
        if level == 2:
            bar = "==="
        else:
            bar = "-"
        return f"{text}\n{bar}\n"

    def paragraph(self, text: str) -> str:
        return text.rstrip() + "\n\n"

    def table(self, table: TableData) -> str:
        header_left, header_right = table.header
        rows = table.rows
        left_w = max(len(str(header_left)), *(len(str(r[0])) for r in rows)) if rows else len(str(header_left))
        right_w = max(len(str(header_right)), *(len(str(r[1])) for r in rows)) if rows else len(str(header_right))

        SEP = "   "
        header_line = f"{str(header_left):<{left_w}}{SEP}{str(header_right):<{right_w}}"
        underline = "-" * len(header_line)

        lines = [header_line, underline]
        for l, r in rows:
            lines.append(f"{str(l):<{left_w}}{SEP}{str(r):<{right_w}}")
        return "\n".join(lines) + "\n"

    def join(self, parts: Iterable[str]) -> str:
        return "".join(parts)


class ReportAdapter(ABC):
    """Turns a domain model into a GenericReport (no rendering)."""

    @abstractmethod
    def supports(self, model: AHPModel | ANPModel) -> bool: ...
    @abstractmethod
    def build(self, model: AHPModel | ANPModel) -> GenericReport: ...


class AHPAdapter(ReportAdapter):
    """Builds a readable AHP report from `AHPModel.to_report_data()`."""

    def supports(self, model: AHPModel | ANPModel) -> bool:
        return hasattr(model, "to_report_data") and "AHP" in type(model).__name__

    def build(self, model: AHPModel) -> GenericReport:
        data: Dict[str, Any] = model.to_report_data()
        sections: List[Section] = []

        crit = data.get("criteria_weights", {})
        sections.append(
            Section(
                title="Criteria Weights",
                tables=[
                    TableData(
                        ("Criterion", "Weight"),
                        [(k, f"{float(v):.6f}") for k, v in crit.items()],
                    )
                ],
            )
        )

        locals_map: Dict[str, List[float]] = data.get("local_alternatives", {})
        alt_names: List[str] = data.get("alternatives", [])
        for c, vec in locals_map.items():
            sections.append(
                Section(
                    title=f"Local Priorities: {c}",
                    tables=[
                        TableData(
                            ("Alternative", "Weight"),
                            list(zip(alt_names, [f"{float(x):.6f}" for x in vec])),
                        )
                    ],
                )
            )

        gp: List[float] = [float(x) for x in data.get("global_priorities", [])]
        ranking_str: str = str(data.get("ranking_str", ""))
        sections.append(
            Section(
                title="Global Priorities",
                tables=[
                    TableData(
                        ("Alternative", "Priority"),
                        list(zip(alt_names, [f"{x:.6f}" for x in gp])),
                    )
                ],
                paragraphs=[f"Ranking: {ranking_str}"],
            )
        )

        # Judgments / Inputs (if present)
        inputs = data.get("inputs", {})
        crit_j = inputs.get("criteria", {}).get("judgments", [])
        if crit_j:
            sections.append(
                Section(
                    title="Pairwise Judgments — Criteria",
                    tables=[
                        TableData(
                            ("i vs j", "ratio"),
                            [
                                (f"{j['i']} > {j['j']}", f"{float(j['value']):.4f}")
                                for j in crit_j
                            ],
                        )
                    ],
                )
            )

        alt_j = inputs.get("alternatives", {})
        for criterion, judg in alt_j.items():
            if not judg:
                continue
            sections.append(
                Section(
                    title=f"Pairwise Judgments — Alternatives under '{criterion}'",
                    tables=[
                        TableData(
                            ("i vs j", "ratio"),
                            [
                                (f"{j['i']} > {j['j']}", f"{float(j['value']):.4f}")
                                for j in judg
                            ],
                        )
                    ],
                )
            )

        return GenericReport(title="AHP Report", sections=sections)


class ANPAdapter(ReportAdapter):
    """Builds a readable ANP report from `ANPModel.to_report_data()`."""

    def supports(self, model: AHPModel | ANPModel) -> bool:
        return hasattr(model, "to_report_data") and "ANP" in type(model).__name__

    def build(self, model: ANPModel) -> GenericReport:
        data: Dict[str, Any] = model.to_report_data()
        sections: List[Section] = []

        cw = data.get("cluster_weights", {})
        sections.append(
            Section(
                title="Cluster Weights",
                tables=[
                    TableData(
                        ("Cluster", "Weight"),
                        [(k, f"{float(v):.6f}") for k, v in cw.items()],
                    )
                ],
            )
        )

        max_dev = float(data.get("max_col_deviation", 0.0))
        sections.append(
            Section(
                title="Sanity Check",
                paragraphs=[f"Column-stochastic check: max |Σcol−1| = {max_dev:.3e}"],
            )
        )

        alt_names: List[str] = data.get("alternatives", [])
        gp: List[float] = [float(x) for x in data.get("global_priorities", [])]
        ranking_str: str = str(data.get("ranking_str", ""))
        sections.append(
            Section(
                title="Alternative Priorities",
                tables=[
                    TableData(
                        ("Alternative", "Priority"),
                        list(zip(alt_names, [f"{x:.6f}" for x in gp])),
                    )
                ],
                paragraphs=[f"Ranking: {ranking_str}"],
            )
        )

        blocks: Dict[str, Any] = data.get("blocks", {})
        for key, meta in blocks.items():
            btype = meta.get("type")
            if btype != "pc_map":
                sections.append(
                    Section(
                        title=f"Block {key} (dense)",
                        paragraphs=[
                            f"Provided as dense matrix with shape {meta.get('shape', '?')} (columns normalized)."
                        ],
                    )
                )
                continue
            entries: Dict[str, List[Dict[str, Any]]] = meta.get("entries", {})
            for src_node, judg in entries.items():
                sections.append(
                    Section(
                        title=f"Block {key} — Judgments for source '{src_node}'",
                        tables=[
                            TableData(
                                ("i vs j", "ratio"),
                                [
                                    (f"{j['i']} > {j['j']}", f"{float(j['value']):.4f}")
                                    for j in judg
                                ],
                            )
                        ],
                    )
                )

        return GenericReport(title="ANP Report", sections=sections)


class AdapterRegistry:
    """Resolves the first adapter that supports the model."""

    def __init__(self) -> None:
        self._adapters: Tuple[ReportAdapter, ...] = (AHPAdapter(), ANPAdapter())

    def resolve(self, model: AHPModel | ANPModel) -> ReportAdapter:
        for adapter in self._adapters:
            if adapter.supports(model):
                return adapter
        raise TypeError(
            f"No ReportAdapter found for model of type {type(model).__name__}"
        )


def _now_stamp() -> str:
    """Return a compact local timestamp like '2025-09-18_21-07-03'."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


class ReportManager:
    """
    Orchestrates building and saving reports.

    - Default base directory is 'reports' (configurable via `base_dir`).
    - Infers extension from renderer (.md / .txt).
    - Appends a timestamp to filenames (configurable).
    - Creates parent directories and writes atomically.
    - Simple rules:
        * path=None            -> save into base_dir with default basename.
        * path is relative     -> interpret under base_dir.
        * path is absolute     -> use as-is.
        * path is directory    -> auto-build filename: <basename>_<ts>.<ext>.
        * path is file (has suffix) -> timestamp only the stem.
    """

    def __init__(
        self,
        renderer: Renderer | None = None,
        *,
        base_dir: str | Path = "reports",
    ) -> None:
        self.renderer: Renderer = renderer or MarkdownRenderer()
        self.base_dir: Path = Path(base_dir).expanduser().resolve()
        self.registry = AdapterRegistry()

    def render(self, model: AHPModel | ANPModel) -> str:
        """Build a `GenericReport` from the model and render it to text."""
        adapter = self.registry.resolve(model)
        generic: GenericReport = adapter.build(model)
        return self.renderer.render(generic)

    def _ext_for_renderer(self) -> str:
        if isinstance(self.renderer, MarkdownRenderer):
            return ".md"
        if isinstance(self.renderer, PlainRenderer):
            return ".txt"
        return ".md"

    def _build_output_path(
        self,
        model: AHPModel | ANPModel,
        path: str | Path | None,
        *,
        basename_if_dir: str | None,
        add_timestamp: bool,
    ) -> Path:
        """
        Resolve the final output path according to the rules in the class docstring.
        """
        default_base = "ahp_report" if "AHP" in type(model).__name__ else "anp_report"

        if path is None:
            out_dir = self.base_dir
            ext = self._ext_for_renderer()
            base = basename_if_dir or default_base
            stamp = f"_{_now_stamp()}" if add_timestamp else ""
            return out_dir / f"{base}{stamp}{ext}"

        target = Path(path).expanduser()
        # Relative targets are interpreted under base_dir
        if not target.is_absolute():
            target = (self.base_dir / target).resolve()

        if target.suffix == "":
            out_dir = target
            ext = self._ext_for_renderer()
            base = basename_if_dir or default_base
            stamp = f"_{_now_stamp()}" if add_timestamp else ""
            return out_dir / f"{base}{stamp}{ext}"
        else:
            out_dir = target.parent
            stem, ext = target.stem, target.suffix
            stamp = f"_{_now_stamp()}" if add_timestamp else ""
            return out_dir / f"{stem}{stamp}{ext}"

    def save(
        self,
        model: AHPModel | ANPModel,
        path: str | Path | None = None,
        *,
        mkdirs: bool = True,
        encoding: str = "utf-8",
        add_timestamp: bool = True,
        basename_if_dir: str | None = None,
    ) -> Path:
        """
        Render and save the report to disk.

        Args:
            model: The AHP/ANP model to report on.
            path:
                - None            -> save to `base_dir` with default basename/ext.
                - Relative path   -> resolved under `base_dir`.
                - Absolute path   -> used as-is.
                - Directory (no suffix) -> auto filename '<basename>_<ts>.<ext>'.
                - File (with suffix)     -> timestamp the stem, keep suffix.
            mkdirs: Create parent directories if needed.
            encoding: File encoding.
            add_timestamp: Whether to append a timestamp to the filename.
            basename_if_dir: Optional override for the auto-generated basename
                             when saving into a directory.

        Returns:
            The final `Path` that was written.
        """
        final_path = self._build_output_path(
            model,
            path,
            basename_if_dir=basename_if_dir,
            add_timestamp=add_timestamp,
        )

        if mkdirs:
            final_path.parent.mkdir(parents=True, exist_ok=True)

        text = self.render(model)
        return atomic_write(text, final_path, mkdirs=False, encoding=encoding)
