from __future__ import annotations

import math
from threading import TIMEOUT_MAX


def is_valid_columns(value: object) -> bool:
    """Return whether *value* is a positive, non-boolean integer."""
    return type(value) is int and value >= 1


def is_bool(value: object) -> bool:
    """Return whether *value* is exactly a boolean."""
    return type(value) is bool


def is_wait_duration(value: object) -> bool:
    """Return whether *value* is supported by platform threading waits."""
    if type(value) is int:
        return 0 <= value <= TIMEOUT_MAX
    if type(value) is float:
        return math.isfinite(value) and 0 <= value <= TIMEOUT_MAX
    return False


def is_playback_fps(value: object) -> bool:
    """Return whether *value* gives a platform-supported frame interval."""
    if type(value) is int:
        return value > 0
    if type(value) is float:
        return math.isfinite(value) and value >= 1 / TIMEOUT_MAX
    return False
