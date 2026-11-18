"""Stateful construction of valid semantic HMM paths."""

from __future__ import annotations

from anihmm._nodes import parse_node_id
from anihmm._symbols import normalize_terminal_symbol
from anihmm._validation import is_valid_columns
from anihmm.exceptions import InvalidTransitionError, SequenceError
from anihmm.models import Step, Transition


class HMMSequence:
    """Stateful builder for semantic HMM animation steps."""

    def __init__(self, *, start: str = "S", columns: int | None = None) -> None:
        """Create a sequence at a canonical node with optional bounds."""
        if columns is not None and not is_valid_columns(columns):
            raise SequenceError("columns must be a positive integer when provided.")
        self._validate_start_node(start, columns)
        self._columns = columns
        self._current_node = start
        self._steps: list[Step] = []
        self._committed: list[Transition] = []
        self._emissions: list[str] = []

    @property
    def columns(self) -> int | None:
        """Configured lattice bound, or ``None`` for an unbounded sequence."""
        return self._columns

    @property
    def current_node(self) -> str:
        """Current settled node identifier."""
        return self._current_node

    @property
    def steps(self) -> list[Step]:
        """Copy of the semantic steps constructed so far."""
        return list(self._steps)

    @property
    def committed(self) -> list[Transition]:
        """Copy of the committed transition path."""
        return list(self._committed)

    @property
    def emissions(self) -> list[str]:
        """Copy of the accumulated emission entries."""
        return list(self._emissions)

    @staticmethod
    def _validate_start_node(start: str, columns: int | None) -> None:
        if not isinstance(start, str):
            raise SequenceError("start must be a node identifier string.")
        parsed = parse_node_id(start)
        if parsed is None:
            raise SequenceError(
                f"Unsupported start node {start!r}; expected 'S', 'E', or a canonical state "
                "such as 'M2'."
            )
        _, parsed_idx = parsed
        if parsed_idx is None:
            return
        idx = parsed_idx
        if columns is not None and idx > columns:
            raise SequenceError(f"Start node {start!r} is outside a {columns}-column lattice.")

    def cycle(self, kind: str, *, title: str | None = None) -> HMMSequence:
        """Add a transient preview of the next state without committing it."""
        target = self._next_node_for(kind)
        resolved_title = self._resolve_title(title, f"Cycle through {target}")
        self._require_current_emission("previewing another transition")
        self._steps.append(
            Step(
                title=resolved_title,
                committed=tuple(self._committed),
                scan=(self.current_node, target),
                emissions=tuple(self._emissions),
            )
        )
        return self

    def settle(self, kind: str, *, title: str | None = None) -> HMMSequence:
        """Commit a transition to the next state of *kind*."""
        target = self._next_node_for(kind)
        resolved_title = self._resolve_title(title, f"Settle on {target}")
        self._require_current_emission("settling another state")
        self._committed.append((self.current_node, target))
        self._current_node = target
        self._steps.append(
            Step(
                title=resolved_title,
                committed=tuple(self._committed),
                emissions=tuple(self._emissions),
            )
        )
        return self

    def emit(self, symbol: str, *, title: str | None = None) -> HMMSequence:
        """Emit one visible terminal-cell symbol from the current state."""
        if not isinstance(symbol, str):
            raise SequenceError("emit() requires a string symbol.")
        normalized_symbol = normalize_terminal_symbol(symbol)
        if normalized_symbol is None:
            raise SequenceError(
                "emit() requires exactly one non-whitespace symbol occupying one terminal cell; "
                f"current node is {self.current_node!r}"
            )
        symbol = normalized_symbol
        parsed_node = parse_node_id(self.current_node)
        if (
            parsed_node is None
            or parsed_node[0] not in {"M", "I"}
            or parsed_node[1] is None
            or (parsed_node[0] == "M" and parsed_node[1] == 0)
            or (self.columns is not None and parsed_node[1] > self.columns)
        ):
            raise SequenceError(
                "emit() is only supported on settled match and insertion states; "
                f"current node is {self.current_node!r}."
            )
        emission_prefix = f"{self.current_node}:"
        if any(emission.startswith(emission_prefix) for emission in self._emissions):
            raise SequenceError(
                f"Node {self.current_node!r} already has an emission; "
                "advance to another emitting state before emitting again."
            )
        resolved_title = self._resolve_title(title, f"Emit {symbol}")
        self._emissions.append(f"{self.current_node}:{symbol}")
        self._steps.append(
            Step(
                title=resolved_title,
                committed=tuple(self._committed),
                emissions=tuple(self._emissions),
            )
        )
        return self

    def flash_current(self, *, title: str | None = None) -> HMMSequence:
        """Add a transient flash overlay to the current state."""
        resolved_title = self._resolve_title(title, f"Flash {self.current_node}")
        self._steps.append(
            Step(
                title=resolved_title,
                committed=tuple(self._committed),
                emissions=tuple(self._emissions),
                flash=(self.current_node,),
            )
        )
        return self

    def finish(self, *, title: str | None = None) -> HMMSequence:
        """Fill remaining bounded columns with deletions, then commit ``E``."""
        resolved_title = self._resolve_title(title, "Settle on E")
        targets = self._finish_targets()
        self._require_current_emission("finishing the sequence")
        for target in targets:
            self._committed.append((self.current_node, target))
            self._current_node = target
            self._steps.append(
                Step(
                    title=resolved_title if target == "E" else f"Settle on {target}",
                    committed=tuple(self._committed),
                    emissions=tuple(self._emissions),
                )
            )
        return self

    def build(self) -> list[Step]:
        """Return a copy of the semantic steps built so far."""
        self._require_current_emission("building the sequence")
        return list(self._steps)

    @staticmethod
    def _resolve_title(title: str | None, default: str) -> str:
        if title is not None and not isinstance(title, str):
            raise SequenceError("title must be a string or None.")
        return title or default

    def _require_current_emission(self, action: str) -> None:
        parsed = parse_node_id(self.current_node)
        if parsed is None or parsed[0] not in {"M", "I"}:
            return
        emission_prefix = f"{self.current_node}:"
        if any(emission.startswith(emission_prefix) for emission in self._emissions):
            return
        raise SequenceError(
            f"Node {self.current_node!r} must emit exactly one symbol before {action}. "
            "Call emit() first."
        )

    def _next_node_for(self, kind: str) -> str:
        if not isinstance(kind, str):
            raise SequenceError("Node kind must be one of the strings 'D', 'M', or 'I'.")
        normalized = kind.strip().upper()
        if normalized not in {"D", "M", "I"}:
            raise SequenceError(
                f"Unsupported node kind {kind!r}; expected one of 'D', 'M', 'I'. "
                f"Current node is {self.current_node!r}."
            )

        if self.current_node == "S":
            return {"D": "D1", "I": "I0", "M": "M1"}[normalized]

        if self.current_node == "E":
            raise SequenceError(
                "Sequence is already finished at 'E'; start a new sequence to continue."
            )

        parsed = parse_node_id(self.current_node)
        if parsed is None:
            raise SequenceError(
                "Unsupported current node "
                f"{self.current_node!r}; expected 'S', 'E', or a state like 'M2'."
            )
        prefix, parsed_idx = parsed
        if parsed_idx is None:
            raise SequenceError(
                f"Unsupported current node {self.current_node!r}; expected a model state."
            )
        idx = parsed_idx

        if prefix in {"M", "D"}:
            target = {
                "D": f"D{idx + 1}",
                "M": f"M{idx + 1}",
                "I": f"I{idx}",
            }[normalized]
            self._validate_target(self.current_node, normalized, target)
            return target

        if prefix == "I":
            if normalized == "I":
                raise SequenceError(
                    "Cannot cycle or settle from "
                    f"{self.current_node!r} to another insertion state directly. "
                    "Use flash_current() to revisit the current insertion, or settle('M') first."
                )
            target = {
                "D": f"D{idx + 1}",
                "M": f"M{idx + 1}",
            }[normalized]
            self._validate_target(self.current_node, normalized, target)
            return target

        raise SequenceError(
            f"Unsupported current node {self.current_node!r} for {kind!r}; "
            "expected a state family of 'D', 'I', or 'M'."
        )

    def _finish_targets(self) -> tuple[str, ...]:
        if self.current_node == "E":
            raise SequenceError("Sequence is already finished at E")

        parsed = parse_node_id(self.current_node)
        if parsed is None:
            raise SequenceError(f"Cannot finish from current node {self.current_node!r}")
        prefix, parsed_idx = parsed

        if self.columns is not None:
            idx = 0 if self.current_node == "S" else parsed_idx
            if idx is None:
                raise SequenceError(f"Cannot finish from current node {self.current_node!r}")
            deletions = tuple(f"D{column}" for column in range(idx + 1, self.columns + 1))
            return (*deletions, "E")

        if parsed_idx is None:
            raise SequenceError(f"Cannot finish from current node {self.current_node!r}")
        idx = parsed_idx
        if prefix == "I" and idx == 0:
            raise SequenceError(
                "Cannot finish directly from 'I0'; advance to the first match or deletion column."
            )
        return ("E",)

    def _validate_target(self, source: str, kind: str, target: str) -> None:
        if self.columns is None:
            return
        suffix = target[1:]
        if not suffix.isdigit():
            return
        idx = int(suffix)
        if idx <= self.columns:
            return

        allowed = self._allowed_kinds_from(source)
        allowed_display = ", ".join(allowed) if allowed else "finish()"
        raise InvalidTransitionError(
            "Cannot move from "
            f"{source!r} via {kind!r}: target {target!r} is outside "
            f"a {self.columns}-column lattice. "
            f"Allowed next actions from {source!r}: {allowed_display}."
        )

    def _allowed_kinds_from(self, node_id: str) -> tuple[str, ...]:
        if node_id == "S":
            return ("D", "I", "M")
        if node_id == "E":
            return ()

        parsed = parse_node_id(node_id)
        if parsed is None:
            return ()
        prefix, parsed_idx = parsed
        if parsed_idx is None:
            return ()
        idx = parsed_idx

        if prefix in {"D", "M"}:
            if self.columns is None:
                return ("D", "M", "I")
            allowed = ["I"]
            if idx < self.columns:
                allowed = ["D", "M", "I"]
            return tuple(allowed)

        if prefix == "I":
            if self.columns is None:
                return ("D", "M")
            if idx < self.columns:
                return ("D", "M")
            return ()

        return ()
