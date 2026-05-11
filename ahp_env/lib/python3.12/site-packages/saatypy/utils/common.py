from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import io
import os
import tempfile

Row = Tuple[str, str]
Header = Tuple[str, str]


def atomic_write(
    text: str,
    path: os.PathLike[str] | str,
    *,
    mkdirs: bool = True,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write `text` to `path` with optional parent creation."""
    p = Path(path)
    if mkdirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=str(p.parent), encoding=encoding
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(p)  # atomic on POSIX
    return p


def fmt_table(rows: List[Row], header: Header, *, markdown: bool) -> str:
    """Two-column table renderer used by renderers."""
    if not markdown:
        w0 = max(len(header[0]), *(len(r[0]) for r in rows)) if rows else len(header[0])
        w1 = max(len(header[1]), *(len(r[1]) for r in rows)) if rows else len(header[1])
        out = io.StringIO()
        out.write(f"{header[0]:<{w0}}  {header[1]:>{w1}}\n")
        out.write("-" * (w0 + w1 + 2) + "\n")
        for a, b in rows:
            out.write(f"{a:<{w0}}  {b:>{w1}}\n")
        return out.getvalue()
    # markdown
    lines = [f"| {header[0]} | {header[1]} |", "|---|---:|"]
    lines += [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines) + "\n"
