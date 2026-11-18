"""Stable-width Rich text rows for the HMM lattice."""

from __future__ import annotations

from rich.text import Text

from anihmm._nodes import parse_node_id
from anihmm.models import HMMFrame

NODE_STYLE = "grey35"
ACTIVE_PARENS_STYLE = "bold white"
START_STYLE = "bold magenta"
EDGE_STYLE = "grey23"
ACTIVE_EDGE_STYLE = "bold white"
EMISSION_STYLE = "bold green"

ACTIVE_LETTER_STYLES = {
    "S": START_STYLE,
    "D": "bold red",
    "I": "bold yellow",
    "M": "bold cyan",
    "E": START_STYLE,
}


def _node(node_id: str, active_nodes: set[str]) -> Text:
    node_kind = node_id if node_id in {"S", "E"} else node_id[0]

    if node_id in active_nodes:
        text = Text("(", style=ACTIVE_PARENS_STYLE)
        text.append(node_kind, style=ACTIVE_LETTER_STYLES.get(node_kind, "bold bright_white"))
        text.append(")", style=ACTIVE_PARENS_STYLE)
        return text

    style = START_STYLE if node_kind == "S" else NODE_STYLE
    text = Text("(", style=style)
    text.append(node_kind, style=style)
    text.append(")", style=style)
    return text


def _append_dim(row: Text, glyph: str) -> None:
    row.append(glyph, style=EDGE_STYLE)


def _build_top_row(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "    ---->")
    row.append_text(_node("D1", frame.active_nodes))
    for idx in range(2, columns + 1):
        _append_dim(row, "-->")
        row.append_text(_node(f"D{idx}", frame.active_nodes))
    _append_dim(row, "-----")
    return row


def _build_upper_row_1(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "   /     ")
    for idx in range(1, columns + 1):
        _append_dim(row, "/|\\")
        if idx < columns:
            _append_dim(row, "/  ")
        else:
            _append_dim(row, "     \\")
    return row


def _build_upper_row_2(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "  /     ")
    for idx in range(1, columns + 1):
        _append_dim(row, "/ |")
        if idx < columns:
            _append_dim(row, "/\\ ")
        else:
            _append_dim(row, " \\     \\")
    return row


def _build_middle_row(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    row.append_text(_node("S", frame.active_nodes))
    _append_dim(row, "-->")
    row.append_text(_node("I0", frame.active_nodes))
    for idx in range(1, columns + 1):
        _append_dim(row, " | ")
        row.append_text(_node(f"I{idx}", frame.active_nodes))
    _append_dim(row, "-->")
    row.append_text(_node("E", frame.active_nodes))
    return row


def _build_lower_row_1(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "  \\     ")
    for idx in range(1, columns + 1):
        _append_dim(row, "\\ |")
        if idx < columns:
            _append_dim(row, "\\/ ")
        else:
            _append_dim(row, " /     /")
    return row


def _build_lower_row_2(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "   \\     ")
    for idx in range(1, columns + 1):
        _append_dim(row, "\\|/")
        if idx < columns:
            _append_dim(row, "\\  ")
        else:
            _append_dim(row, "     /")
    return row


def _build_bottom_row(frame: HMMFrame, columns: int) -> Text:
    row = Text()
    _append_dim(row, "    ---->")
    row.append_text(_node("M1", frame.active_nodes))
    for idx in range(2, columns + 1):
        _append_dim(row, "-->")
        row.append_text(_node(f"M{idx}", frame.active_nodes))
    _append_dim(row, "-----")
    return row


def _pad_rows(rows: list[Text]) -> list[Text]:
    width = max(row.cell_len for row in rows)
    padded: list[Text] = []
    for row in rows:
        if row.cell_len < width:
            row.append(" " * (width - row.cell_len), style=EDGE_STYLE)
        padded.append(row)
    return padded


def _find_node_col(lines: list[Text], node_label: str) -> tuple[int, int] | None:
    for row_idx, row in enumerate(lines):
        plain = row.plain
        for col in range(1, len(plain)):
            if plain[col] == node_label and plain[col - 1] == "(":
                return row_idx, col
    return None


def _find_nth_node_col(row: Text, letter: str, occurrence: int) -> int | None:
    if occurrence < 1:
        return None
    count = 0
    plain = row.plain
    for col in range(1, len(plain)):
        if plain[col] == letter and plain[col - 1] == "(":
            count += 1
            if count == occurrence:
                return col
    return None


def resolve_node_anchor(lines: list[Text], node_id: str) -> tuple[int, int] | None:
    """Resolve a canonical node identifier to its letter cell."""
    node_id = node_id.strip()
    if not node_id:
        return None

    if node_id == "S":
        col = _find_nth_node_col(lines[3], "S", 1)
        return (3, col) if col is not None else None

    if node_id == "E":
        col = _find_nth_node_col(lines[3], "E", 1)
        return (3, col) if col is not None else None

    parsed = parse_node_id(node_id)
    if parsed is not None and parsed[1] is not None:
        kind, parsed_idx = parsed
        if parsed_idx is None:
            return None
        idx = parsed_idx
        if kind == "M":
            col = _find_nth_node_col(lines[6], "M", idx)
            return (6, col) if col is not None else None
        if kind == "D":
            col = _find_nth_node_col(lines[0], "D", idx)
            return (0, col) if col is not None else None
        if kind == "I":
            col = _find_nth_node_col(lines[3], "I", idx + 1)
            return (3, col) if col is not None else None

    if len(node_id) == 1:
        return _find_node_col(lines, node_id)
    return None


def build_lattice_rows(frame: HMMFrame, columns: int) -> list[Text]:
    """Build and right-pad the seven graph rows for *frame*."""
    return _pad_rows(
        [
            _build_top_row(frame, columns),
            _build_upper_row_1(frame, columns),
            _build_upper_row_2(frame, columns),
            _build_middle_row(frame, columns),
            _build_lower_row_1(frame, columns),
            _build_lower_row_2(frame, columns),
            _build_bottom_row(frame, columns),
        ]
    )


def base_lattice_rows(columns: int) -> list[Text]:
    """Build inactive lattice rows for a column count."""
    return build_lattice_rows(HMMFrame(), columns)
