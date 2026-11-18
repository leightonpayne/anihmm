"""Public exception hierarchy for anihmm."""

from __future__ import annotations


class AnihmmError(Exception):
    """Base exception for public anihmm API failures."""


class AnimationConfigError(AnihmmError, ValueError):
    """Invalid playback or rendering configuration."""


class SequenceError(AnihmmError, ValueError):
    """Invalid semantic sequence construction."""


class InvalidTransitionError(SequenceError):
    """Invalid lattice transition or node reference."""


class FrameCompilationError(AnihmmError, ValueError):
    """Failure while compiling semantic steps into renderable frames."""


class SessionError(AnihmmError, RuntimeError):
    """Failure while starting, stopping, or monitoring a background session."""


class AnimationTimeoutError(SessionError, TimeoutError):
    """Animation session did not finish before the requested timeout."""


__all__ = [
    "AnihmmError",
    "AnimationConfigError",
    "AnimationTimeoutError",
    "FrameCompilationError",
    "InvalidTransitionError",
    "SequenceError",
    "SessionError",
]
