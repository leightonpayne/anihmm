from __future__ import annotations

from rich.cells import cell_len


def normalize_terminal_symbol(value: object) -> str | None:
    """Return a stripped one-cell symbol, or ``None`` when invalid."""
    if not isinstance(value, str):
        return None
    symbol = value.strip()
    if len(symbol) != 1 or cell_len(symbol) != 1:
        return None
    return symbol
