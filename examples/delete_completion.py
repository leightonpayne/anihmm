"""Finish a partial bounded path through automatic deletion states."""

from __future__ import annotations

from rich.console import Console

from anihmm import AnimationSession, HMMFrame, HMMSequence, compile_steps

COLUMNS = 8
FPS = 8.0


def build_delete_completion_frames() -> list[HMMFrame]:
    sequence = HMMSequence(columns=COLUMNS)
    sequence.settle("M").emit("A")
    sequence.settle("I").emit("C")
    sequence.settle("M").emit("G")
    sequence.finish()

    start = HMMFrame(columns=COLUMNS, active_nodes={"S"})
    return [start, *compile_steps(sequence.build(), columns=COLUMNS)]


def main(console: Console | None = None) -> None:
    console = console or Console()
    with AnimationSession(
        build_delete_completion_frames(),
        fps=FPS,
        repeat=False,
        console=console,
    ) as session:
        session.wait()


if __name__ == "__main__":
    main()
