"""Compilation of semantic steps into renderable frame descriptions."""

from __future__ import annotations

from collections.abc import Iterable

from anihmm._nodes import parse_node_id
from anihmm._validation import is_valid_columns
from anihmm.exceptions import FrameCompilationError, InvalidTransitionError
from anihmm.models import GridCell, HMMFrame, Step, Transition
from anihmm.render.emissions import _resolve_emission_positions
from anihmm.render.geometry import flash_overlay_cells, transition_cells
from anihmm.render.rows import base_lattice_rows


def _validate_transition(value: object, *, field: str) -> Transition:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not all(isinstance(node_id, str) for node_id in value)
    ):
        raise FrameCompilationError(f"{field} must be a two-item tuple of node identifier strings.")
    return value


def _validate_step(step: object) -> Step:
    if not isinstance(step, Step):
        raise FrameCompilationError(f"Expected Step; got {type(step).__name__}.")
    if not isinstance(step.title, str):
        raise FrameCompilationError("Step title must be a string.")
    if not isinstance(step.committed, tuple):
        raise FrameCompilationError("Step committed transitions must be a tuple.")
    for idx, transition in enumerate(step.committed, start=1):
        _validate_transition(transition, field=f"Committed transition #{idx}")
    if step.scan is not None:
        _validate_transition(step.scan, field="Scan transition")
    if not isinstance(step.emissions, tuple) or not all(
        isinstance(emission, str) for emission in step.emissions
    ):
        raise FrameCompilationError("Step emissions must be a tuple of strings.")
    if not isinstance(step.flash, tuple) or not all(
        isinstance(node_id, str) for node_id in step.flash
    ):
        raise FrameCompilationError("Step flash nodes must be a tuple of strings.")
    return step


def _node_index(node_id: str) -> int | None:
    parsed = parse_node_id(node_id)
    return parsed[1] if parsed is not None else None


def _infer_columns_from_step(step: Step) -> int:
    columns = 1

    transitions = step.committed + ((step.scan,) if step.scan is not None else ())
    for source, target in transitions:
        source_idx = _node_index(source)
        target_idx = _node_index(target)
        if source_idx is not None:
            columns = max(columns, source_idx)
        if target != "E" and target_idx is not None:
            columns = max(columns, target_idx)

    for emission in step.emissions:
        anchor = emission.split(":", 1)[0].strip()
        anchor_idx = _node_index(anchor)
        if anchor_idx is not None:
            columns = max(columns, anchor_idx)

    for node_id in step.flash:
        node_idx = _node_index(node_id)
        if node_idx is not None:
            columns = max(columns, node_idx)

    return columns


def _resolve_columns(steps: Iterable[Step], columns: int | None) -> tuple[list[Step], int]:
    try:
        iterator = iter(steps)
    except TypeError as exc:
        raise FrameCompilationError("steps must be an iterable of Step objects.") from exc
    steps_list = list(iterator)
    for idx, step in enumerate(steps_list, start=1):
        try:
            _validate_step(step)
        except FrameCompilationError as exc:
            raise FrameCompilationError(f"Invalid step #{idx}: {exc}") from exc
    if columns is not None:
        if not is_valid_columns(columns):
            raise FrameCompilationError("columns must be a positive integer when provided.")
        return steps_list, columns
    inferred = max((_infer_columns_from_step(step) for step in steps_list), default=1)
    return steps_list, inferred


def _nodes_from_transitions(transitions: Iterable[Transition]) -> set[str]:
    nodes: set[str] = set()
    for source, target in transitions:
        nodes.add(source)
        nodes.add(target)
    return nodes


def _validate_transition_continuity(step: Step) -> None:
    for index in range(1, len(step.committed)):
        previous_target = step.committed[index - 1][1]
        source = step.committed[index][0]
        if source != previous_target:
            raise FrameCompilationError(
                f"Committed transition #{index + 1} starts at {source!r}, but the preceding "
                f"transition ends at {previous_target!r}."
            )
    if step.scan is not None and step.committed:
        current_node = step.committed[-1][1]
        if step.scan[0] != current_node:
            raise FrameCompilationError(
                f"Scan transition starts at {step.scan[0]!r}, but the committed path ends at "
                f"{current_node!r}."
            )


def compile_step(step: Step, *, columns: int | None = None) -> HMMFrame:
    """Compile one semantic step into a renderable frame description."""
    step = _validate_step(step)
    _validate_transition_continuity(step)
    resolved_columns = _infer_columns_from_step(step) if columns is None else columns
    if not is_valid_columns(resolved_columns):
        raise FrameCompilationError("columns must be a positive integer when provided.")
    transitions = step.committed + ((step.scan,) if step.scan is not None else ())
    active_cells: set[GridCell] = set()
    for source, target in transitions:
        try:
            active_cells.update(transition_cells(resolved_columns, source, target))
        except InvalidTransitionError as exc:
            raise FrameCompilationError(
                "Failed to compile step "
                f"{step.title!r}: invalid transition {source}->{target}. {exc}"
            ) from exc

    try:
        glyph_overlays = dict(
            flash_overlay_cells(resolved_columns, node_id) for node_id in step.flash
        )
    except InvalidTransitionError as exc:
        raise FrameCompilationError(f"Failed to compile step {step.title!r}: {exc}") from exc

    try:
        _resolve_emission_positions(base_lattice_rows(resolved_columns), step.emissions)
    except FrameCompilationError as exc:
        raise FrameCompilationError(
            f"Failed to compile step {step.title!r}: invalid emissions. {exc}"
        ) from exc

    return HMMFrame(
        columns=resolved_columns,
        active_nodes=_nodes_from_transitions(transitions),
        active_cells=active_cells,
        glyph_overlays=glyph_overlays,
        emissions=list(step.emissions),
    )


def compile_steps(steps: Iterable[Step], *, columns: int | None = None) -> list[HMMFrame]:
    """Compile semantic steps with a shared explicit or inferred column count."""
    steps_list, resolved_columns = _resolve_columns(steps, columns)
    frames: list[HMMFrame] = []
    for idx, step in enumerate(steps_list, start=1):
        try:
            frames.append(compile_step(step, columns=resolved_columns))
        except FrameCompilationError as exc:
            raise FrameCompilationError(
                f"Failed to compile step #{idx} ({step.title!r}): {exc}"
            ) from exc
    return frames
