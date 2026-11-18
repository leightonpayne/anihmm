"""Build an exact HMM path and play it around a block of work."""

from __future__ import annotations

from rich.console import Console

from anihmm import AnimationSession, HMMFrame, HMMSequence, compile_steps

COLUMNS = 8
FPS = 10.0


def build_custom_frames() -> list[HMMFrame]:
    sequence = HMMSequence(columns=COLUMNS)
    for state, symbol in (
        ("M", "C"),
        ("I", "U"),
        ("M", "S"),
        ("D", None),
        ("M", "T"),
        ("D", None),
        ("M", "O"),
        ("D", None),
        ("M", "M"),
    ):
        sequence.settle(state)
        if symbol is not None:
            sequence.emit(symbol)
    sequence.finish()

    start = HMMFrame(columns=COLUMNS, active_nodes={"S"})
    return [start, *compile_steps(sequence.build(), columns=COLUMNS)]


def main(console: Console | None = None) -> None:
    console = console or Console()
    with AnimationSession(
        build_custom_frames(),
        fps=FPS,
        repeat=False,
        console=console,
    ) as session:
        session.wait()


if __name__ == "__main__":
    main()
