"""Animate a small block of dummy work and return placeholder results."""

from __future__ import annotations

import time

from rich.console import Console

from anihmm import PlaybackOptions, ProcessingOptions
from anihmm.models import HMMFrame
from anihmm.playback import print_frame_in_place, processing_animation
from anihmm.presets import build_random_path_frame

COLUMNS = 7
FPS = 16.0
WORK_SECONDS = 5.5
SEARCH_EMISSIONS = "SEARCHING"
COMPLETE_EMISSIONS = "COMPLETE"
SEARCH_SEED = 13
COMPLETE_SEED = 23
DUMMY_HIT_COUNTS = (1, 0, 1, 1, 0, 2, 3, 1, 0, 1, 3, 2)


def build_search_options(*, seed: int | None = SEARCH_SEED) -> ProcessingOptions:
    """Return the processing configuration shown by this example."""

    return ProcessingOptions.random(
        columns=COLUMNS,
        seed=seed,
        emissions=SEARCH_EMISSIONS,
    )


def build_complete_frame(*, seed: int | None = COMPLETE_SEED) -> HMMFrame:
    """Build the completed frame printed after the work finishes."""

    if seed is None:
        return build_random_path_frame(
            columns=COLUMNS,
            emissions=COMPLETE_EMISSIONS,
        )
    return build_random_path_frame(
        columns=COLUMNS,
        seed=seed,
        emissions=COMPLETE_EMISSIONS,
    )


def run_demo(console: Console | None = None) -> list[int]:
    """Wait briefly inside an animation and return dummy HMM hit counts."""

    console = console or Console()
    with processing_animation(
        build_search_options(),
        PlaybackOptions.background(
            fps=FPS,
            console=console,
        ),
    ):
        time.sleep(WORK_SECONDS)
        hit_counts = list(DUMMY_HIT_COUNTS)

    print_frame_in_place(
        build_complete_frame(),
        console=console,
    )
    return hit_counts


def summarize_results(hit_counts: list[int]) -> tuple[int, int, int]:
    """Return HMMs searched, HMMs with hits, and total hits."""

    return (
        len(hit_counts),
        sum(count > 0 for count in hit_counts),
        sum(hit_counts),
    )


def result_lines(hit_counts: list[int]) -> tuple[str, str, str]:
    """Format the three result lines printed after the animation."""

    hmms_searched, hmms_with_hits, total_hits = summarize_results(hit_counts)
    hmm_label = "HMM" if hmms_with_hits == 1 else "HMMs"
    return (
        f"Searched {hmms_searched} HMMs",
        f"{hmms_with_hits} {hmm_label} produced hits",
        f"{total_hits} total hits",
    )


def main(console: Console | None = None) -> list[int]:
    """Run the complete terminal example and return its dummy hit counts."""

    console = console or Console()
    console.print("")
    hit_counts = run_demo(console)
    console.print("")
    for line in result_lines(hit_counts):
        console.print(line)
    return hit_counts


if __name__ == "__main__":
    main()
