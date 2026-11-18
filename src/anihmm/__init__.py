"""Application-facing API for terminal HMM animations."""

from .exceptions import (
    AnihmmError,
    AnimationConfigError,
    AnimationTimeoutError,
    FrameCompilationError,
    InvalidTransitionError,
    SequenceError,
    SessionError,
)
from .models import HMMFrame
from .playback import (
    AnimationSession,
    AsyncAnimationSession,
    PlaybackOptions,
    ProcessingOptions,
    ProgressSession,
    animate_frames,
    async_loading_animation,
    async_processing_animation,
    loading_animation,
    print_frame_in_place,
    processing_animation,
    progress_animation,
)
from .sequence import HMMSequence, compile_steps

__all__ = [
    "AnimationSession",
    "AnimationConfigError",
    "AnimationTimeoutError",
    "AnihmmError",
    "AsyncAnimationSession",
    "FrameCompilationError",
    "HMMFrame",
    "HMMSequence",
    "InvalidTransitionError",
    "PlaybackOptions",
    "ProcessingOptions",
    "ProgressSession",
    "SequenceError",
    "SessionError",
    "async_loading_animation",
    "async_processing_animation",
    "animate_frames",
    "compile_steps",
    "loading_animation",
    "print_frame_in_place",
    "progress_animation",
    "processing_animation",
]
