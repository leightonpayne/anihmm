"""Keep fixed text while choosing a fresh random path on each loop."""

from __future__ import annotations

import time

from rich.console import Console

from anihmm import AnimationSession, HMMFrame, ProcessingOptions

COLUMNS = 8
EMISSIONS = "WAITING"
FPS = 16.0
SEED = 5
PATH_COUNT = 3
WORK_SECONDS = 2.2


def build_options(*, seed: int | None = SEED) -> ProcessingOptions:
    """Return the processing configuration shown by this example."""

    return ProcessingOptions.random(columns=COLUMNS, seed=seed, emissions=EMISSIONS)


def build_changing_frames() -> list[HMMFrame]:
    """Build three reproducible paths from the incrementing frame source."""

    source = build_options().frame_source()
    return [frame for _ in range(PATH_COUNT) for frame in source()]


def wait_for_results() -> None:
    """Stand in for longer work while several paths are displayed."""
    time.sleep(WORK_SECONDS)


def main(console: Console | None = None) -> None:
    console = console or Console()
    with AnimationSession(
        build_changing_frames(),
        fps=FPS,
        repeat=False,
        console=console,
    ) as session:
        wait_for_results()
        session.wait()


if __name__ == "__main__":
    main()
