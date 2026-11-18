"""Show fixed text on a reproducible random HMM path."""

from __future__ import annotations

import time

from rich.console import Console

from anihmm import PlaybackOptions, ProcessingOptions, processing_animation

COLUMNS = 8
SEED = 11
EMISSIONS = "LOADING"
FPS = 16.0
WORK_SECONDS = 0.6


def build_options(*, seed: int | None = SEED) -> ProcessingOptions:
    """Return the processing configuration shown by this example."""

    return ProcessingOptions.random(columns=COLUMNS, seed=seed, emissions=EMISSIONS)


def load_records() -> None:
    """Stand in for application work performed while the status is visible."""
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
        load_records()
        session.wait()


if __name__ == "__main__":
    main()
