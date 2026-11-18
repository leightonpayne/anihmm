"""Work-driven HMM progress playback."""

from __future__ import annotations

from threading import Condition, Lock, Thread
from time import monotonic
from types import TracebackType

from rich.console import Console
from rich.live import Live

from anihmm._symbols import normalize_terminal_symbol
from anihmm._validation import is_bool, is_playback_fps, is_valid_columns, is_wait_duration
from anihmm.exceptions import (
    AnimationConfigError,
    AnimationTimeoutError,
    SequenceError,
    SessionError,
)
from anihmm.models import HMMFrame
from anihmm.playback import engine as playback_engine
from anihmm.playback.options import DEFAULT_FPS
from anihmm.sequence import HMMSequence, compile_step

_SCAN_ORDER = ("D", "I", "M")
_DEFAULT_SETTLE_SECONDS = 0.25


class ProgressSession:
    """Cycle candidate transitions until application work advances the path."""

    def __init__(
        self,
        *,
        columns: int = 8,
        fps: float = DEFAULT_FPS,
        settle_seconds: float = _DEFAULT_SETTLE_SECONDS,
        console: Console | None = None,
        enabled: bool | None = None,
        alternate_screen: bool = False,
    ) -> None:
        """Create a single-use progress session for a bounded HMM lattice."""
        if not is_valid_columns(columns):
            raise AnimationConfigError("columns must be a positive integer.")
        if not is_playback_fps(fps):
            raise AnimationConfigError(
                "fps must be a positive finite number with a platform-supported frame interval."
            )
        if not is_wait_duration(settle_seconds):
            raise AnimationConfigError(
                "settle_seconds must be a non-negative, platform-supported wait duration."
            )
        if console is not None and not isinstance(console, Console):
            raise AnimationConfigError("console must be a rich Console or None.")
        if enabled is not None and not is_bool(enabled):
            raise AnimationConfigError("enabled must be a boolean or None.")
        if not is_bool(alternate_screen):
            raise AnimationConfigError("alternate_screen must be a boolean.")

        self._columns = columns
        self._fps = fps
        self._settle_seconds = settle_seconds
        self._console = console or Console()
        self._enabled = bool(self._console.is_terminal) if enabled is None else enabled
        self._alternate_screen = alternate_screen

        self._sequence = HMMSequence(columns=columns)
        self._settled_frame = HMMFrame(columns=columns, active_nodes={"S"})
        self._scan_frames = self._build_scan_frames()
        self._version = 0
        self._rendered_version = -1
        self._held_version = -1

        self._condition = Condition(Lock())
        self._lifecycle_lock = Lock()
        self._thread: Thread | None = None
        self._error: BaseException | None = None
        self._started = False
        self._stop_requested = False
        self._finished = False

    def __enter__(self) -> ProgressSession:
        """Start scanning transitions on context entry."""
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Stop playback while preserving exceptions raised by the work block."""
        self.stop()
        if exc_type is not None:
            try:
                self.wait()
            except (AnimationTimeoutError, SessionError):
                return
            return
        self.wait()

    @property
    def current_node(self) -> str:
        """The most recently settled node."""
        with self._condition:
            return self._sequence.current_node

    @property
    def is_finished(self) -> bool:
        """Whether :meth:`finish` has committed the path to ``E``."""
        with self._condition:
            return self._finished

    @property
    def is_running(self) -> bool:
        """Whether terminal playback is active in the worker thread."""
        with self._condition:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> ProgressSession:
        """Start scanning and return this session."""
        with self._lifecycle_lock:
            with self._condition:
                if self._started:
                    raise SessionError("ProgressSession is single-use and has already started.")
                self._started = True
                if not self._enabled:
                    self._rendered_version = self._version
                    self._held_version = self._version
                    return self
                self._thread = Thread(
                    target=self._run,
                    name="anihmm-progress-session",
                    daemon=True,
                )
                self._thread.start()
        return self

    def advance(self, kind: str, *, emission: str | None = None) -> ProgressSession:
        """Settle on the chosen state, then begin scanning its outgoing transitions."""
        normalized_kind, normalized_emission = self._validate_advance(kind, emission)
        with self._condition:
            self._require_active()
            self._sequence.settle(normalized_kind)
            if normalized_emission is not None:
                self._sequence.emit(normalized_emission)
            self._settled_frame = compile_step(
                self._sequence.steps[-1],
                columns=self._columns,
            )
            self._scan_frames = self._build_scan_frames()
            version = self._publish_update()
            self._wait_for_presentation(version, held=False)
        return self

    def finish(self) -> ProgressSession:
        """Commit the current path to ``E`` and hold its completed frame."""
        with self._condition:
            self._require_active()
            self._sequence.finish()
            self._settled_frame = compile_step(
                self._sequence.steps[-1],
                columns=self._columns,
            )
            self._scan_frames = ()
            self._finished = True
            version = self._publish_update()
            self._wait_for_presentation(version, held=True)
        return self

    def stop(self) -> None:
        """Request cooperative cancellation of terminal playback."""
        with self._condition:
            self._stop_requested = True
            self._condition.notify_all()

    def wait(self, timeout: float | None = None) -> None:
        """Wait for playback to stop and surface timeout or worker errors."""
        if timeout is not None and not is_wait_duration(timeout):
            raise AnimationConfigError(
                "timeout must be a non-negative, platform-supported wait duration when provided."
            )
        with self._lifecycle_lock:
            with self._condition:
                thread = self._thread
            if thread is not None:
                thread.join(timeout)
                if thread.is_alive():
                    raise AnimationTimeoutError(
                        "ProgressSession did not finish before the requested timeout."
                    )
            with self._condition:
                if self._thread is thread:
                    self._thread = None
                self._raise_worker_error()

    def _build_scan_frames(self) -> tuple[HMMFrame, ...]:
        frames: list[HMMFrame] = []
        for kind in _SCAN_ORDER:
            try:
                self._sequence.cycle(kind)
            except SequenceError:
                continue
            frames.append(
                compile_step(
                    self._sequence.steps[-1],
                    columns=self._columns,
                )
            )
        if self._sequence.current_node.startswith("I") and len(frames) == 2:
            self._sequence.flash_current()
            flash_frame = compile_step(
                self._sequence.steps[-1],
                columns=self._columns,
            )
            return (frames[0], flash_frame, frames[1], flash_frame)
        return tuple([*frames, *reversed(frames[1:-1])])

    @staticmethod
    def _validate_advance(kind: str, emission: str | None) -> tuple[str, str | None]:
        if not isinstance(kind, str):
            raise SequenceError("Node kind must be one of the strings 'D', 'M', or 'I'.")
        normalized_kind = kind.strip().upper()
        if normalized_kind not in {"D", "M", "I"}:
            raise SequenceError(
                f"Unsupported node kind {kind!r}; expected one of 'D', 'M', or 'I'."
            )
        if normalized_kind == "D":
            if emission is not None:
                raise SequenceError("Deletion states do not emit; pass emission=None.")
            return normalized_kind, None
        if emission is None:
            raise SequenceError(
                f"{normalized_kind} states require exactly one terminal-cell emission."
            )
        if not isinstance(emission, str):
            raise SequenceError("emission must be a string or None.")
        normalized_emission = normalize_terminal_symbol(emission)
        if normalized_emission is None:
            raise SequenceError(
                "emission must be exactly one non-whitespace symbol occupying one terminal cell."
            )
        return normalized_kind, normalized_emission

    def _require_active(self) -> None:
        self._raise_worker_error()
        if not self._started:
            raise SessionError("ProgressSession must be started before it can advance.")
        if self._stop_requested:
            raise SessionError("ProgressSession has been stopped.")
        if self._finished:
            raise SessionError("ProgressSession is already finished at 'E'.")

    def _raise_worker_error(self) -> None:
        if self._error is None:
            return
        error = self._error
        self._error = None
        raise SessionError("ProgressSession failed.") from error

    def _publish_update(self) -> int:
        self._version += 1
        if not self._enabled:
            self._rendered_version = self._version
            self._held_version = self._version
        self._condition.notify_all()
        return self._version

    def _wait_for_presentation(self, version: int, *, held: bool) -> None:
        attribute = "_held_version" if held else "_rendered_version"
        while getattr(self, attribute) < version:
            self._raise_worker_error()
            if self._stop_requested:
                raise SessionError("ProgressSession stopped before presenting the requested state.")
            self._condition.wait()

    def _run(self) -> None:
        try:
            self._render_loop()
        except BaseException as exc:  # pragma: no cover - surfaced by the public methods
            with self._condition:
                self._error = exc
                self._stop_requested = True
                self._condition.notify_all()

    def _render_loop(self) -> None:
        with self._condition:
            version = self._version
            settled_frame = self._settled_frame
        renderable = playback_engine._render_for_console(
            settled_frame,
            columns=self._columns,
            console=self._console,
        )
        refresh_rate = max(4, int(min(self._fps, 30) * 2))
        with Live(
            renderable,
            console=self._console,
            auto_refresh=False,
            refresh_per_second=refresh_rate,
            screen=self._alternate_screen,
        ) as live:
            with self._condition:
                initial_frame_rendered = version == self._version
                if initial_frame_rendered:
                    self._rendered_version = version
                    self._condition.notify_all()
            while True:
                with self._condition:
                    if self._stop_requested:
                        return
                    version = self._version
                    settled_frame = self._settled_frame
                    scan_frames = self._scan_frames
                    if initial_frame_rendered:
                        initial_frame_rendered = False
                    else:
                        live.update(
                            playback_engine._render_for_console(
                                settled_frame,
                                columns=self._columns,
                                console=self._console,
                            ),
                            refresh=True,
                        )
                        self._rendered_version = version
                        self._condition.notify_all()

                if self._wait_for_change(version, self._settle_seconds):
                    continue
                with self._condition:
                    if version == self._version:
                        self._held_version = version
                        self._condition.notify_all()

                frame_index = 0
                while True:
                    with self._condition:
                        if self._stop_requested:
                            return
                        if version != self._version:
                            break
                        if not scan_frames:
                            self._condition.wait()
                            continue
                        frame = scan_frames[frame_index % len(scan_frames)]
                        live.update(
                            playback_engine._render_for_console(
                                frame,
                                columns=self._columns,
                                console=self._console,
                            ),
                            refresh=True,
                        )
                    if self._wait_for_change(version, 1 / self._fps):
                        break
                    frame_index += 1

    def _wait_for_change(self, version: int, seconds: float) -> bool:
        deadline = monotonic() + seconds
        with self._condition:
            while not self._stop_requested and version == self._version:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True


def progress_animation(
    *,
    columns: int = 8,
    fps: float = DEFAULT_FPS,
    settle_seconds: float = _DEFAULT_SETTLE_SECONDS,
    console: Console | None = None,
    enabled: bool | None = None,
    alternate_screen: bool = False,
) -> ProgressSession:
    """Build a work-driven progress session for use as a context manager."""
    return ProgressSession(
        columns=columns,
        fps=fps,
        settle_seconds=settle_seconds,
        console=console,
        enabled=enabled,
        alternate_screen=alternate_screen,
    )


__all__ = ["ProgressSession", "progress_animation"]
