"""Cell geometry for supported HMM lattice transitions."""

from __future__ import annotations

from functools import lru_cache

from anihmm._validation import is_valid_columns
from anihmm.exceptions import FrameCompilationError, InvalidTransitionError
from anihmm.models import GlyphOverlay, GridCell
from anihmm.render.rows import ACTIVE_EDGE_STYLE, base_lattice_rows, resolve_node_anchor


@lru_cache(maxsize=64)
def _node_anchor_map(columns: int) -> dict[str, GridCell]:
    lines = base_lattice_rows(columns)
    anchors: dict[str, GridCell] = {}

    for node_id in ["S", "E"]:
        anchor = resolve_node_anchor(lines, node_id)
        if anchor is None:
            raise FrameCompilationError(f"Could not resolve anchor for {node_id}")
        anchors[node_id] = anchor

    node_rows = {"D": 0, "I": 3, "M": 6}
    expected_counts = {"D": columns, "I": columns + 1, "M": columns}
    for prefix, row_idx in node_rows.items():
        node_columns = _node_letter_columns(lines[row_idx].plain, prefix)
        if len(node_columns) != expected_counts[prefix]:
            raise FrameCompilationError(
                f"Could not resolve all {prefix} anchors for a {columns}-column lattice"
            )
        start_index = 0 if prefix == "I" else 1
        for offset, col in enumerate(node_columns):
            anchors[f"{prefix}{start_index + offset}"] = (row_idx, col)

    return anchors


def _node_letter_columns(row: str, letter: str) -> list[int]:
    return [col for col in range(1, len(row)) if row[col] == letter and row[col - 1] == "("]


def _span_cells(row: int, start: int, end: int) -> set[GridCell]:
    left, right = sorted((start, end))
    return {(row, col) for col in range(left, right + 1)}


def _column_cells(col: int, start: int, end: int) -> set[GridCell]:
    top, bottom = sorted((start, end))
    return {(row, col) for row in range(top, bottom + 1)}


def _diag_cells(start: GridCell, d_row: int, d_col: int, steps: int) -> set[GridCell]:
    row, col = start
    return {(row + step * d_row, col + step * d_col) for step in range(1, steps + 1)}


def transition_cells(columns: int, source: str, target: str) -> set[GridCell]:
    """Return lattice cells belonging to one supported state transition."""
    if not is_valid_columns(columns):
        raise InvalidTransitionError("columns must be a positive integer")
    if not isinstance(source, str) or not isinstance(target, str):
        raise InvalidTransitionError("source and target must be node identifier strings")
    anchors = _node_anchor_map(columns)
    if source not in anchors or target not in anchors:
        raise InvalidTransitionError(
            f"Unsupported transition {source}->{target} for a {columns}-column lattice. "
            f"Known nodes include: S, I0..I{columns}, D1..D{columns}, M1..M{columns}, E."
        )

    src_row, src_col = anchors[source]
    dst_row, dst_col = anchors[target]
    src_kind = source[0]
    dst_kind = target[0]
    src_idx = int(source[1:]) if source[1:].isdigit() else None
    dst_idx = int(target[1:]) if target[1:].isdigit() else None

    if source == "S" and target == "D1":
        return _diag_cells((src_row, src_col), -1, 1, 2) | _span_cells(
            dst_row, src_col + 3, dst_col - 2
        )

    if source == "S" and target == "I0":
        return _span_cells(src_row, src_col + 2, dst_col - 2)

    if source == "S" and target == "M1":
        return _diag_cells((src_row, src_col), 1, 1, 2) | _span_cells(
            dst_row, src_col + 3, dst_col - 2
        )

    if (
        src_kind == dst_kind
        and src_kind in {"D", "M"}
        and src_idx is not None
        and dst_idx == src_idx + 1
    ):
        return _span_cells(src_row, src_col + 2, dst_col - 2)

    if src_kind == "M" and dst_kind == "I" and src_idx == dst_idx:
        return _diag_cells((src_row, src_col), -1, 1, 2)

    if src_kind == "I" and dst_kind == "M" and src_idx is not None and dst_idx == src_idx + 1:
        return _diag_cells((src_row, src_col), 1, 1, 2)

    if src_kind == "I" and dst_kind == "D" and src_idx is not None and dst_idx == src_idx + 1:
        return _diag_cells((src_row, src_col), -1, 1, 2)

    if src_kind == "D" and dst_kind == "I" and dst_idx == src_idx:
        return _diag_cells((src_row, src_col), 1, 1, 2)

    if src_kind == "D" and dst_kind == "M" and src_idx is not None and dst_idx == src_idx + 1:
        vertical = _column_cells(src_col, src_row + 1, src_row + 3)
        diagonal = {(src_row + 4, src_col + 1), (src_row + 5, src_col + 2)}
        bottom = _span_cells(dst_row, src_col + 3, dst_col - 2)
        return vertical | diagonal | bottom

    if src_kind == "M" and dst_kind == "D" and src_idx is not None and dst_idx == src_idx + 1:
        vertical = _column_cells(src_col, dst_row + 3, src_row - 1)
        diagonal = {(src_row - 4, src_col + 1), (src_row - 5, src_col + 2)}
        top = _span_cells(dst_row, src_col + 3, dst_col - 2)
        return vertical | diagonal | top

    if target == "E" and src_idx == columns:
        if src_kind == "D":
            return _span_cells(src_row, src_col + 2, src_col + 6) | {
                (src_row + 1, src_col + 7),
                (src_row + 2, src_col + 8),
            }
        if src_kind == "I":
            return _span_cells(src_row, src_col + 2, dst_col - 2)
        if src_kind == "M":
            return _span_cells(src_row, src_col + 2, src_col + 6) | {
                (src_row - 2, src_col + 8),
                (src_row - 1, src_col + 7),
            }

    raise InvalidTransitionError(
        f"Unsupported transition {source}->{target} for a {columns}-column lattice. "
        "Supported families include S->D1/I0/M1, D->D/I/M, M->D/I/M, I->D/M, "
        "and terminal *->E from the last column."
    )


def flash_overlay_cells(columns: int, node_id: str) -> tuple[GridCell, GlyphOverlay]:
    """Return the glyph overlay used to flash a lattice node."""
    if not is_valid_columns(columns):
        raise InvalidTransitionError("columns must be a positive integer")
    if not isinstance(node_id, str):
        raise InvalidTransitionError("node_id must be a node identifier string")
    anchor = _node_anchor_map(columns).get(node_id)
    if anchor is None:
        raise InvalidTransitionError(
            f"Unsupported scan flash node {node_id!r} for a {columns}-column lattice. "
            f"Expected S, I0..I{columns}, D1..D{columns}, M1..M{columns}, or E."
        )
    row, col = anchor
    return (row, col + 2), ("<", ACTIVE_EDGE_STYLE)
