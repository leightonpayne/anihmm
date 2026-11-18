"""Advance an HMM path as individual units of work complete."""

from __future__ import annotations

import time

from rich.console import Console

from anihmm import ProgressSession, progress_animation

COLUMNS = 8
FPS = 8.0
SETTLE_SECONDS = 0.25
STEP_SECONDS = 2
PATH: tuple[tuple[str, str | None], ...] = (
    ("M", "P"),
    ("I", "R"),
    ("M", "O"),
    ("D", None),
    ("M", "G"),
    ("I", "R"),
    ("M", "E"),
    ("D", None),
    ("M", "S"),
    ("M", "S"),
)


def run_step() -> None:
    """Stand in for one unit of application work."""
    time.sleep(STEP_SECONDS)


def advance_path(session: ProgressSession) -> None:
    """Advance the configured path as each unit of work completes."""
    for state, emission in PATH:
        run_step()
        session.advance(state, emission=emission)
    session.finish()


def main(console: Console | None = None) -> None:
    console = console or Console()
    with progress_animation(
        columns=COLUMNS,
        fps=FPS,
        settle_seconds=SETTLE_SECONDS,
        console=console,
    ) as session:
        advance_path(session)


if __name__ == "__main__":
    main()
