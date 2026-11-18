"""Finite random HMM path and frame generation."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

from anihmm._nodes import parse_node_id
from anihmm._symbols import normalize_terminal_symbol
from anihmm._validation import is_valid_columns
from anihmm.exceptions import AnimationConfigError, SequenceError
from anihmm.models import HMMFrame, Step
from anihmm.sequence import HMMSequence, compile_step, compile_steps

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
EmissionSpec = int | str | None
_PathEvent = tuple[str, str, str | None]


def _random_action_choices(current_node: str, *, columns: int) -> list[str]:
    if current_node == "S":
        return ["D", "I", "M"]
    if current_node == "E":
        return []

    parsed = parse_node_id(current_node)
    if parsed is None:
        raise SequenceError(f"Unsupported current node {current_node!r} for random path generation")
    prefix, parsed_idx = parsed
    if parsed_idx is None:
        raise SequenceError(f"Unsupported current node {current_node!r} for random path generation")
    idx = parsed_idx

    if prefix in {"D", "M"}:
        choices = ["I"]
        if idx < columns:
            choices = ["D", "M", "I"]
        if idx == columns:
            choices.append("E")
        return choices

    if prefix == "I":
        if idx < columns:
            return ["D", "M"]
        return ["E"]

    raise SequenceError(f"Unsupported current node {current_node!r} for random path generation")


def _random_target_for_action(current_node: str, action: str, *, columns: int) -> str:
    return HMMSequence(start=current_node, columns=columns)._next_node_for(action)


def _emits_on_settle(node_id: str) -> bool:
    return node_id.startswith(("M", "I"))


def _normalize_emission_spec(emissions: EmissionSpec) -> tuple[int | None, list[str] | None]:
    if emissions is None:
        return None, None
    if type(emissions) is int:
        if emissions < 0:
            raise SequenceError(f"emissions must be >= 0; got {emissions}.")
        return emissions, None
    if type(emissions) is str:
        symbols = list(emissions)
        invalid_symbol = next(
            (symbol for symbol in symbols if normalize_terminal_symbol(symbol) is None), None
        )
        if invalid_symbol is not None:
            raise SequenceError(
                "Each requested emission must be a non-whitespace symbol occupying one "
                f"terminal cell; got {invalid_symbol!r}."
            )
        return len(symbols), symbols
    raise SequenceError("emissions must be an integer count, a string, or None.")


def _reachable_emission_counts(current_node: str, columns: int) -> range:
    if current_node == "E":
        return range(1)
    if current_node == "S":
        maximum = 2 * columns + 1
        return range(maximum + 1)

    parsed = parse_node_id(current_node)
    if parsed is None:
        raise SequenceError(f"Unsupported current node {current_node!r} for emission planning")
    prefix, parsed_idx = parsed
    if parsed_idx is None:
        raise SequenceError(f"Unsupported current node {current_node!r} for emission planning")
    idx = parsed_idx
    if idx > columns:
        raise SequenceError(f"Current node {current_node!r} is outside a {columns}-column lattice.")
    maximum = 2 * (columns - idx) + (1 if prefix in {"D", "M"} else 0)
    return range(maximum + 1)


def _random_action_choices_for_emissions(
    current_node: str,
    *,
    columns: int,
    remaining_emissions: int,
) -> list[str]:
    valid_actions: list[str] = []

    for action in _random_action_choices(current_node, columns=columns):
        if action == "E":
            if remaining_emissions == 0:
                valid_actions.append(action)
            continue

        target = _random_target_for_action(current_node, action, columns=columns)
        emitted = 1 if _emits_on_settle(target) else 0
        if remaining_emissions < emitted:
            continue
        if remaining_emissions - emitted in _reachable_emission_counts(target, columns):
            valid_actions.append(action)

    return valid_actions


def _plan_random_path(
    *,
    columns: int,
    seed: int | None,
    emissions: EmissionSpec,
) -> list[_PathEvent]:
    if seed is not None and type(seed) is not int:
        raise SequenceError("seed must be an integer or None.")
    if not is_valid_columns(columns):
        raise SequenceError("columns must be a positive integer.")
    # This RNG controls visual animation paths, not security-sensitive values.
    rng = random.Random(seed)  # nosec B311
    current_node = "S"
    remaining_emissions, emission_symbols = _normalize_emission_spec(emissions)
    emitted_index = 0
    events: list[_PathEvent] = []

    if remaining_emissions is not None:
        reachable = _reachable_emission_counts("S", columns)
        if remaining_emissions not in reachable:
            requested = (
                f"the exact emission sequence {emissions!r}"
                if isinstance(emissions, str)
                else f"exactly {remaining_emissions} emissions"
            )
            raise SequenceError(
                f"Cannot generate a random path with {requested} in a {columns}-column lattice. "
                f"Reachable emission counts range from {min(reachable)} to {max(reachable)}."
            )

    while current_node != "E":
        if remaining_emissions is None:
            choices = _random_action_choices(current_node, columns=columns)
        else:
            choices = _random_action_choices_for_emissions(
                current_node,
                columns=columns,
                remaining_emissions=remaining_emissions,
            )
        choice = rng.choice(choices)
        if choice == "E":
            events.append((current_node, "E", None))
            break

        target = _random_target_for_action(current_node, choice, columns=columns)
        symbol: str | None = None
        if _emits_on_settle(target):
            symbol = (
                emission_symbols[emitted_index]
                if emission_symbols is not None
                else rng.choice(AMINO_ACIDS)
            )
            if emission_symbols is not None:
                emitted_index += 1
            if remaining_emissions is not None:
                remaining_emissions -= 1
        events.append((current_node, target, symbol))
        current_node = target

    return events


def build_random_steps(
    *,
    columns: int = 5,
    seed: int | None = None,
    emissions: EmissionSpec = None,
) -> list[Step]:
    """Build a finite random semantic path through a bounded HMM lattice."""
    events = _plan_random_path(columns=columns, seed=seed, emissions=emissions)
    sequence = HMMSequence(columns=columns)

    for _source, target, symbol in events:
        if target == "E":
            sequence.finish()
            continue
        sequence.cycle(target[0])
        sequence.settle(target[0])
        if symbol is not None:
            sequence.emit(symbol)

    return sequence.build()


def _prepend_start_frame(frames: Sequence[HMMFrame]) -> list[HMMFrame]:
    columns = frames[0].columns if frames else 5
    return [HMMFrame(columns=columns, active_nodes={"S"}), *frames]


def build_random_frames(
    *,
    columns: int = 5,
    seed: int | None = None,
    emissions: EmissionSpec = None,
) -> list[HMMFrame]:
    """Build a start frame and compiled frames for a finite random path."""
    steps = build_random_steps(columns=columns, seed=seed, emissions=emissions)
    return _prepend_start_frame(compile_steps(steps, columns=columns))


def build_random_path_frame(
    *,
    columns: int = 5,
    seed: int | None = None,
    emissions: EmissionSpec = None,
) -> HMMFrame:
    """Return the final settled frame from a generated random path."""
    events = _plan_random_path(columns=columns, seed=seed, emissions=emissions)
    committed = tuple((source, target) for source, target, _symbol in events)
    final_emissions = tuple(
        f"{target}:{symbol}" for _source, target, symbol in events if symbol is not None
    )
    return compile_step(
        Step(
            title="Settle on E",
            committed=committed,
            emissions=final_emissions,
        ),
        columns=columns,
    )


def extend_frames(existing: Iterable[HMMFrame], *new_frames: HMMFrame) -> list[HMMFrame]:
    """Return a new frame list containing *existing* followed by *new_frames*."""
    try:
        iterator = iter(existing)
    except TypeError as exc:
        raise AnimationConfigError("existing must be an iterable of HMMFrame objects.") from exc
    frames = list(iterator)
    frames.extend(new_frames)
    invalid_index = next(
        (index for index, frame in enumerate(frames) if not isinstance(frame, HMMFrame)),
        None,
    )
    if invalid_index is not None:
        raise AnimationConfigError(
            f"Expected HMMFrame at combined frame index {invalid_index}; "
            f"got {type(frames[invalid_index]).__name__}."
        )
    return frames
