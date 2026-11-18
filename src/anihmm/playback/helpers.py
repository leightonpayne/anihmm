"""Convenience constructors for configured animation sessions."""

from __future__ import annotations

from anihmm.exceptions import AnimationConfigError
from anihmm.playback.options import PlaybackOptions, ProcessingOptions
from anihmm.playback.session import AnimationSession, AsyncAnimationSession


def processing_animation(
    processing: ProcessingOptions | None = None,
    playback: PlaybackOptions | None = None,
) -> AnimationSession:
    """Build a synchronous background animation session from reusable options."""
    if processing is not None and not isinstance(processing, ProcessingOptions):
        raise AnimationConfigError("processing must be a ProcessingOptions instance or None.")
    if playback is not None and not isinstance(playback, PlaybackOptions):
        raise AnimationConfigError("playback must be a PlaybackOptions instance or None.")
    processing = ProcessingOptions.demo() if processing is None else processing
    playback = PlaybackOptions.background() if playback is None else playback
    return AnimationSession(
        processing.frame_source(),
        options=playback,
    )


loading_animation = processing_animation


def async_processing_animation(
    processing: ProcessingOptions | None = None,
    playback: PlaybackOptions | None = None,
) -> AsyncAnimationSession:
    """Build an asynchronous background animation session from reusable options."""
    if processing is not None and not isinstance(processing, ProcessingOptions):
        raise AnimationConfigError("processing must be a ProcessingOptions instance or None.")
    if playback is not None and not isinstance(playback, PlaybackOptions):
        raise AnimationConfigError("playback must be a PlaybackOptions instance or None.")
    processing = ProcessingOptions.demo() if processing is None else processing
    playback = PlaybackOptions.background() if playback is None else playback
    return AsyncAnimationSession(
        processing.frame_source(),
        options=playback,
    )


async_loading_animation = async_processing_animation
