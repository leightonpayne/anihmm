"""Threaded synchronous and asynchronous animation sessions."""

from __future__ import annotations

import asyncio
from threading import Event, Lock, Thread
from types import TracebackType

from rich.console import Console

from anihmm._validation import is_wait_duration
from anihmm.exceptions import AnimationConfigError, AnimationTimeoutError, SessionError
from anihmm.models import FrameSource, HMMFrame
from anihmm.playback.engine import _materialize_frames, animate_frames
from anihmm.playback.options import DEFAULT_FPS, PlaybackOptions


def _reusable_frame_factory(frames: FrameSource) -> FrameSource:
    """Cache a non-callable frame iterable after its first successful materialization."""
    if callable(frames):
        return frames

    cached_frames: list[HMMFrame] | None = None
    cache_lock = Lock()

    def frame_factory() -> list[HMMFrame]:
        nonlocal cached_frames
        with cache_lock:
            if cached_frames is None:
                cached_frames = _materialize_frames(frames, factory=False)
            return cached_frames

    return frame_factory


class AnimationSession:
    """Background animation session for embedding in terminal workflows."""

    def __init__(
        self,
        frames: FrameSource,
        *,
        options: PlaybackOptions | None = None,
        fps: float = DEFAULT_FPS,
        columns: int | None = None,
        repeat: bool = True,
        hold_final_seconds: float | None = None,
        console: Console | None = None,
        enabled: bool | None = None,
        alternate_screen: bool = False,
    ) -> None:
        """Create a reusable background session for *frames*."""
        if options is not None and not isinstance(options, PlaybackOptions):
            raise AnimationConfigError("options must be a PlaybackOptions instance or None.")
        self._frames = _reusable_frame_factory(frames)
        self._options = (
            options
            if options is not None
            else PlaybackOptions(
                fps=fps,
                columns=columns,
                repeat=repeat,
                hold_final_seconds=hold_final_seconds,
                console=console,
                enabled=enabled,
                alternate_screen=alternate_screen,
            )
        )
        self._stop_event = Event()
        self._lock = Lock()
        self._thread: Thread | None = None
        self._error: BaseException | None = None

    def __enter__(self) -> AnimationSession:
        """Start the session on context entry."""
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the session and preserve any exception from the context body."""
        self.stop()
        if exc_type is not None:
            try:
                self.wait()
            except (AnimationTimeoutError, SessionError):
                return
            return
        self.wait()

    @property
    def is_running(self) -> bool:
        """Whether the current worker thread is alive."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> AnimationSession:
        """Start playback in a background thread and return this session."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise SessionError("AnimationSession is already running.")
            if self._error is not None:
                error = self._error
                self._error = None
                raise SessionError("The previous AnimationSession run failed.") from error

            self._stop_event.clear()
            self._thread = Thread(target=self._run, name="anihmm-session", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        """Request cooperative cancellation of the active run."""
        self._stop_event.set()

    def wait(self, timeout: float | None = None) -> None:
        """Wait for the active run and surface its timeout or worker error."""
        if timeout is not None and not is_wait_duration(timeout):
            raise AnimationConfigError(
                "timeout must be a non-negative, platform-supported wait duration when provided."
            )

        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                raise AnimationTimeoutError(
                    "AnimationSession did not finish before the requested timeout."
                )
        with self._lock:
            # A finished run can be restarted while this waiter is joining it.
            # Its waiter must not clear the new worker or consume the new error.
            if self._thread is not thread:
                return
            self._thread = None
            error = self._error
            self._error = None
        if error is not None:
            raise SessionError("AnimationSession failed.") from error

    def _run(self) -> None:
        try:
            animate_frames(
                self._frames,
                fps=self._options.fps,
                columns=self._options.columns,
                repeat=self._options.repeat,
                hold_final_seconds=self._options.hold_final_seconds,
                console=self._options.console,
                stop_event=self._stop_event,
                enabled=self._options.enabled,
                alternate_screen=self._options.alternate_screen,
            )
        except BaseException as exc:  # pragma: no cover - surfaced through wait()
            with self._lock:
                self._error = exc


class AsyncAnimationSession:
    """Async wrapper around :class:`AnimationSession`."""

    def __init__(
        self,
        frames: FrameSource,
        *,
        options: PlaybackOptions | None = None,
        fps: float = DEFAULT_FPS,
        columns: int | None = None,
        repeat: bool = True,
        hold_final_seconds: float | None = None,
        console: Console | None = None,
        enabled: bool | None = None,
        alternate_screen: bool = False,
    ) -> None:
        """Create an async wrapper around a background animation session."""
        self._session = AnimationSession(
            frames,
            options=options,
            fps=fps,
            columns=columns,
            repeat=repeat,
            hold_final_seconds=hold_final_seconds,
            console=console,
            enabled=enabled,
            alternate_screen=alternate_screen,
        )

    async def __aenter__(self) -> AsyncAnimationSession:
        """Start the wrapped session on async context entry."""
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop the session and preserve any exception from the context body."""
        self.stop()
        if exc_type is not None:
            try:
                await self.wait()
            except (AnimationTimeoutError, SessionError):
                return
            return
        await self.wait()

    @property
    def is_running(self) -> bool:
        """Whether the wrapped worker thread is alive."""
        return self._session.is_running

    async def start(self) -> AsyncAnimationSession:
        """Start the wrapped background session and return this wrapper."""
        self._session.start()
        return self

    def stop(self) -> None:
        """Request cooperative cancellation of the wrapped session."""
        self._session.stop()

    async def wait(self, timeout: float | None = None) -> None:
        """Await completion and surface timeout or worker errors."""
        await asyncio.to_thread(self._session.wait, timeout)
