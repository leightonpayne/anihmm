"""Assembly and validation of complete Rich lattice frames."""

from __future__ import annotations

import textwrap

from rich.console import Group

from anihmm._validation import is_valid_columns
from anihmm.exceptions import AnimationConfigError, FrameCompilationError
from anihmm.models import MASK_MARKERS, GridCell, HMMFrame
from anihmm.render.emissions import apply_emissions, overlay_char
from anihmm.render.rows import (
    ACTIVE_EDGE_STYLE,
    base_lattice_rows,
    build_lattice_rows,
)


def cells_from_mask(
    mask: str, *, markers: set[str] | frozenset[str] = MASK_MARKERS
) -> set[GridCell]:
    """Convert marked characters in a dedented text mask to grid coordinates."""
    if not isinstance(mask, str):
        raise AnimationConfigError("mask must be a string.")
    if not isinstance(markers, (set, frozenset)) or not all(
        isinstance(marker, str) and len(marker) == 1 for marker in markers
    ):
        raise AnimationConfigError("markers must be a set or frozenset of single characters.")
    normalized = textwrap.dedent(mask).strip("\n")
    if not normalized:
        return set()

    cells: set[GridCell] = set()
    for row_idx, line in enumerate(normalized.splitlines()):
        for col_idx, ch in enumerate(line):
            if ch in markers:
                cells.add((row_idx, col_idx))
    return cells


def _apply_cell_overrides(lines, frame: HMMFrame) -> None:
    for row_idx, col_idx in frame.active_cells:
        if row_idx < 0 or row_idx >= len(lines):
            raise FrameCompilationError(f"active_cells row out of range: {(row_idx, col_idx)}")
        if col_idx < 0 or col_idx >= lines[row_idx].cell_len:
            raise FrameCompilationError(f"active_cells column out of range: {(row_idx, col_idx)}")
        lines[row_idx].stylize(ACTIVE_EDGE_STYLE, col_idx, col_idx + 1)

    for (row_idx, col_idx), style in frame.cell_styles.items():
        if row_idx < 0 or row_idx >= len(lines):
            raise FrameCompilationError(f"cell_styles row out of range: {(row_idx, col_idx)}")
        if col_idx < 0 or col_idx >= lines[row_idx].cell_len:
            raise FrameCompilationError(f"cell_styles column out of range: {(row_idx, col_idx)}")
        lines[row_idx].stylize(style, col_idx, col_idx + 1)


def _apply_glyph_overlays(lines, frame: HMMFrame) -> None:
    for (row_idx, col_idx), (glyph, style) in frame.glyph_overlays.items():
        if row_idx < 0 or row_idx >= len(lines):
            raise FrameCompilationError(f"glyph_overlays row out of range: {(row_idx, col_idx)}")
        if col_idx < 0 or col_idx >= lines[row_idx].cell_len:
            raise FrameCompilationError(f"glyph_overlays column out of range: {(row_idx, col_idx)}")
        lines[row_idx] = overlay_char(lines[row_idx], col_idx, glyph, style)


def lattice_guide(columns: int = 5) -> str:
    """Return a numbered plain-text guide for lattice cell coordinates."""
    if not is_valid_columns(columns):
        raise AnimationConfigError("columns must be a positive integer")
    rows = [row.plain for row in base_lattice_rows(columns)]
    width = max(len(row) for row in rows)
    rows = [row.ljust(width) for row in rows]
    ruler = "    " + "".join(str(idx % 10) for idx in range(width))
    body = "\n".join(f"{idx:02}  {row}" for idx, row in enumerate(rows))
    return f"{ruler}\n{body}"


def _resolve_frame_columns(frame: HMMFrame, columns: int | None) -> int:
    if columns is not None:
        return columns
    if frame.columns is not None:
        return frame.columns
    return 5


def _validate_active_nodes(frame: HMMFrame, columns: int) -> None:
    known_nodes = {"S", "E", *(f"I{idx}" for idx in range(columns + 1))}
    known_nodes.update(f"D{idx}" for idx in range(1, columns + 1))
    known_nodes.update(f"M{idx}" for idx in range(1, columns + 1))
    unknown_nodes = frame.active_nodes - known_nodes
    if unknown_nodes:
        display = ", ".join(sorted(unknown_nodes))
        raise FrameCompilationError(
            f"Unknown active node(s) for a {columns}-column lattice: {display}."
        )


def render_frame(frame: HMMFrame, columns: int | None = None) -> Group:
    """Render an :class:`HMMFrame` as a stable-height Rich group."""
    if not isinstance(frame, HMMFrame):
        raise AnimationConfigError(f"frame must be an HMMFrame; got {type(frame).__name__}.")
    frame._validate_structure()
    columns = _resolve_frame_columns(frame, columns)
    if not is_valid_columns(columns):
        raise AnimationConfigError("columns must be a positive integer")

    _validate_active_nodes(frame, columns)
    lines = build_lattice_rows(frame, columns)
    anchor_lines = [line.copy() for line in lines]
    _apply_cell_overrides(lines, frame)
    _apply_glyph_overlays(lines, frame)
    apply_emissions(lines, frame.emissions, anchor_lines=anchor_lines)
    return Group(*lines)
