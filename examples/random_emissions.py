"""Emit an exact number of random amino-acid symbols on a random path."""

from __future__ import annotations

import time

from rich.console import Console

from anihmm import PlaybackOptions, ProcessingOptions, processing_animation

COLUMNS = 8
SEED = 3
EMISSIONS = 7
FPS = 16.0
WORK_SECONDS = 0.6


def build_options(*, seed: int | None = SEED) -> ProcessingOptions:
    """Return the processing configuration shown by this example."""

    return ProcessingOptions.random(columns=COLUMNS, seed=seed, emissions=EMISSIONS)


def analyze_sequences() -> None:
    """Stand in for application work performed while symbols are emitted."""
    time.sleep(WORK_SECONDS)


def main(console: Console | None = None) -> None:
    console = console or Console()
    with processing_animation(
        build_options(),
        PlaybackOptions(
            fps=FPS,
            repeat=False,
            console=console,
        ),
    ) as session:
        analyze_sequences()
        session.wait()


if __name__ == "__main__":
    main()
