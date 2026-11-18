"""Emission parsing and terminal-row overlays."""

from __future__ import annotations

from rich.cells import cell_len, set_cell_size
from rich.text import Text

from anihmm._nodes import parse_node_id
from anihmm.exceptions import FrameCompilationError
from anihmm.render.rows import EMISSION_STYLE, resolve_node_anchor

_ResolvedEmission = tuple[bool, str, str, int, int]


def overlay_char(text: Text, col: int, ch: str, style: str) -> Text:
    """Return *text* with one terminal cell replaced when *col* is in range."""
    if cell_len(ch) != 1:
        raise FrameCompilationError(f"Overlay glyph {ch!r} must occupy exactly one terminal cell.")
    if col < 0 or col >= text.cell_len:
        return text
    before_offset = _codepoint_offset_for_cell(text.plain, col)
    after_offset = _codepoint_offset_for_cell(text.plain, col + 1)
    before = text[:before_offset]
    after = text[after_offset:] if col + 1 < text.cell_len else Text()
    return before + Text(ch, style=style) + after


def _codepoint_offset_for_cell(value: str, cells: int) -> int:
    """Return the furthest code-point boundary within a terminal-cell offset."""
    prefix = set_cell_size(value, cells)
    if cell_len(prefix) != cells or value[: len(prefix)] != prefix:
        raise FrameCompilationError(
            "Overlay column intersects a glyph occupying multiple terminal cells."
        )
    return len(prefix)


def parse_emission_entry(entry: str) -> tuple[str, str, int | None]:
    """Parse an anchored emission or legacy positional label."""
    stripped = entry.strip()
    if not stripped:
        return "", "", None

    if ":" in stripped:
        anchor, label = stripped.split(":", 1)
        anchor = anchor.strip()
        label = label.strip()
        if not anchor or not label:
            raise FrameCompilationError(
                f"Explicit emission {entry!r} requires both an anchor and a label."
            )
        return anchor, label, None

    idx = next((i for i, c in enumerate(entry) if c not in (" ", ".", ":")), None)
    if idx is None:
        return "", "", None
    label = entry[idx]
    return label, label, idx


def apply_emissions(
    lines: list[Text],
    emissions: list[str],
    *,
    anchor_lines: list[Text] | None = None,
) -> list[Text]:
    """Append connector and label rows for emission entries."""
    anchor_lines = lines if anchor_lines is None else anchor_lines
    width = max(row.cell_len for row in lines)
    graph_height = len(lines)
    connector_row = Text(" " * width, style=EMISSION_STYLE)
    label_row = Text(" " * width, style=EMISSION_STYLE)
    resolved_emissions = _resolve_emission_positions(anchor_lines, emissions)

    for explicit_anchor, anchor_id, label, node_row, node_col in resolved_emissions:
        if explicit_anchor and anchor_id.startswith("I"):
            for row_idx in range(node_row + 1, graph_height):
                lines[row_idx] = overlay_char(lines[row_idx], node_col, ":", EMISSION_STYLE)

        connector_row = overlay_char(connector_row, node_col, ":", EMISSION_STYLE)
        label_row = overlay_char(label_row, node_col, label, EMISSION_STYLE)

    lines.append(connector_row)
    lines.append(label_row)
    return lines


def _resolve_emission_positions(
    anchor_lines: list[Text], emissions: list[str] | tuple[str, ...]
) -> list[_ResolvedEmission]:
    """Validate emissions and resolve their graph positions without mutating rows."""
    resolved: list[_ResolvedEmission] = []
    used_anchors: set[str] = set()

    for emission in emissions:
        explicit_anchor = ":" in emission.strip()
        anchor_id, label, fallback_col = parse_emission_entry(emission)
        if not label:
            continue
        if cell_len(label) != 1:
            raise FrameCompilationError(
                f"Overlay glyph {label!r} must occupy exactly one terminal cell."
            )
        if explicit_anchor:
            parsed_anchor = parse_node_id(anchor_id)
            if parsed_anchor is None or parsed_anchor[0] not in {"M", "I"}:
                raise FrameCompilationError(
                    f"Emission anchor {anchor_id!r} must be a match or insertion state with a "
                    "canonical identifier."
                )
            if anchor_id in used_anchors:
                raise FrameCompilationError(
                    f"Emission anchor {anchor_id!r} is used more than once in one frame."
                )
            used_anchors.add(anchor_id)
            found = resolve_node_anchor(anchor_lines, anchor_id)
            if found is None:
                raise FrameCompilationError(
                    f"Could not resolve emission anchor {anchor_id!r} for emission {emission!r}."
                )
            node_row, node_col = found
        else:
            node_row = 0
            node_col = fallback_col if fallback_col is not None else 0
        resolved.append((explicit_anchor, anchor_id, label, node_row, node_col))

    return resolved
