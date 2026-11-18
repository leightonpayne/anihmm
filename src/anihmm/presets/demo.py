"""Deterministic default demo preset."""

from __future__ import annotations

from anihmm._validation import is_valid_columns
from anihmm.exceptions import SequenceError
from anihmm.models import HMMFrame
from anihmm.presets.random import build_random_frames

DEMO_COLUMNS = 8
DEMO_EMISSIONS = "SEARCHING"
DEMO_SEED = 0


def build_demo_frames(
    *, columns: int = DEMO_COLUMNS, seed: int | None = DEMO_SEED
) -> list[HMMFrame]:
    """Build the deterministic demo, shortening its label for small lattices."""
    if not is_valid_columns(columns):
        raise SequenceError("columns must be a positive integer.")
    emissions = DEMO_EMISSIONS[: 2 * columns + 1]
    return build_random_frames(columns=columns, seed=seed, emissions=emissions)
