"""Preview every legal transition before settling on a chosen state."""

from __future__ import annotations

from rich.console import Console

from anihmm import AnimationSession, HMMFrame, HMMSequence, compile_steps

COLUMNS = 8
FPS = 10.0


def build_transition_preview_frames() -> list[HMMFrame]:
    sequence = HMMSequence(columns=COLUMNS)
    for candidates, state, symbol in (
        (("D", "I", "M"), "M", "A"),
        (("D", "I", "M"), "I", "C"),
        (("D", "M"), "M", "G"),
        (("D", "I", "M"), "D", None),
        (("D", "I", "M"), "M", "T"),
        (("D", "I", "M"), "M", "A"),
        (("D", "I", "M"), "D", None),
        (("D", "I", "M"), "M", "C"),
        (("D", "I", "M"), "M", "G"),
    ):
        for candidate in candidates:
            sequence.cycle(candidate)
        sequence.settle(state)
        if symbol is not None:
            sequence.emit(symbol)
    sequence.finish()

    start = HMMFrame(columns=COLUMNS, active_nodes={"S"})
    return [start, *compile_steps(sequence.build(), columns=COLUMNS)]


def main(console: Console | None = None) -> None:
    console = console or Console()
    with AnimationSession(
        build_transition_preview_frames(),
        fps=FPS,
        repeat=False,
        console=console,
    ) as session:
        session.wait()


if __name__ == "__main__":
    main()
