"""Shared public frame and semantic-step data models."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from anihmm._validation import is_valid_columns
from anihmm.exceptions import AnimationConfigError

GridCell = tuple[int, int]
GlyphOverlay = tuple[str, str]
Transition = tuple[str, str]
MASK_MARKERS = frozenset({"x", "X", "#", "*", "@"})


@dataclass(slots=True)
class HMMFrame:
    """A single renderable HMM lattice frame."""

    columns: int | None = None
    active_nodes: set[str] = field(default_factory=set)
    active_cells: set[GridCell] = field(default_factory=set)
    cell_styles: dict[GridCell, str] = field(default_factory=dict)
    glyph_overlays: dict[GridCell, GlyphOverlay] = field(default_factory=dict)
    emissions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate the initial frame structure."""
        if self.columns is not None and not is_valid_columns(self.columns):
            raise AnimationConfigError("columns must be a positive integer when provided.")
        self._validate_structure()

    def _validate_structure(self) -> None:
        if not isinstance(self.active_nodes, set) or not all(
            isinstance(node_id, str) for node_id in self.active_nodes
        ):
            raise AnimationConfigError("active_nodes must be a set of node identifier strings.")
        if not isinstance(self.active_cells, set) or not all(
            _is_grid_cell(cell) for cell in self.active_cells
        ):
            raise AnimationConfigError("active_cells must be a set of integer coordinate tuples.")
        if not isinstance(self.cell_styles, dict) or not all(
            _is_grid_cell(cell) and isinstance(style, str)
            for cell, style in self.cell_styles.items()
        ):
            raise AnimationConfigError(
                "cell_styles must map integer coordinate tuples to style strings."
            )
        if not isinstance(self.glyph_overlays, dict) or not all(
            _is_grid_cell(cell)
            and isinstance(overlay, tuple)
            and len(overlay) == 2
            and all(isinstance(value, str) for value in overlay)
            for cell, overlay in self.glyph_overlays.items()
        ):
            raise AnimationConfigError(
                "glyph_overlays must map integer coordinate tuples to glyph/style string tuples."
            )
        if not isinstance(self.emissions, list) or not all(
            isinstance(emission, str) for emission in self.emissions
        ):
            raise AnimationConfigError("emissions must be a list of strings.")


def _is_grid_cell(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(type(coordinate) is int for coordinate in value)
    )


FrameSource = Iterable[HMMFrame] | Callable[[], Iterable[HMMFrame]]


@dataclass(frozen=True, slots=True)
class Step:
    """Semantic description of one animation beat."""

    title: str
    committed: tuple[Transition, ...] = ()
    scan: Transition | None = None
    emissions: tuple[str, ...] = ()
    flash: tuple[str, ...] = ()
