"""Synchronous Rich rendering and frame playback."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from threading import Event
from typing import cast

from rich.console import Console, Group
from rich.control import Control
from rich.errors import MissingStyle
from rich.live import Live
from rich.segment import ControlType
from rich.text import Text

from anihmm._validation import is_bool, is_playback_fps, is_valid_columns, is_wait_duration
from anihmm.exceptions import AnimationConfigError, FrameCompilationError
from anihmm.models import FrameSource, HMMFrame
from anihmm.playback.options import DEFAULT_FPS
from anihmm.render import render_frame


def _render_for_console(frame: HMMFrame, *, columns: int | None, console: Console) -> Group:
    """Render a frame without allowing terminal autowrap to change its height."""
    rendered = render_frame(frame, columns=columns)
    terminal_width = max(console.size.width, 1)
    rows: list[Text] = []
    style_names: set[str] = set()
    for renderable in rendered.renderables:
        row = cast(Text, renderable).copy()
        if isinstance(row.style, str) and row.style:
            style_names.add(row.style)
        style_names.update(
            span.style for span in row.spans if isinstance(span.style, str) and span.style
        )
        row.truncate(terminal_width, overflow="crop", pad=False)
        row.no_wrap = True
        rows.append(row)
    for style_name in style_names:
        try:
            console.get_style(style_name)
        except MissingStyle as exc:
            raise FrameCompilationError(
                f"Style {style_name!r} is not available in the target console theme."
            ) from exc
    return Group(*rows)


def _materialize_frames(value: object, *, factory: bool) -> list[HMMFrame]:
    source_label = "frame factory" if factory else "frames"
    try:
        iterator = iter(cast(Iterable[object], value))
    except TypeError as exc:
        raise AnimationConfigError(
            f"Expected {source_label} to provide an iterable of HMMFrame objects."
        ) from exc
    items = list(iterator)
    if not items:
        raise AnimationConfigError(f"Expected at least one frame from {source_label}.")
    invalid_index = next(
        (index for index, item in enumerate(items) if not isinstance(item, HMMFrame)),
        None,
    )
    if invalid_index is not None:
        raise AnimationConfigError(
            f"Expected HMMFrame at {source_label} index {invalid_index}; "
            f"got {type(items[invalid_index]).__name__}."
        )
    return cast(list[HMMFrame], items)


def print_frame_in_place(
    frame: HMMFrame,
    *,
    console: Console | None = None,
    columns: int | None = None,
) -> None:
    """Replace the previous fixed-height lattice region with *frame*."""
    if console is not None and not isinstance(console, Console):
        raise AnimationConfigError("console must be a rich Console or None.")
    console = Console() if console is None else console
    renderable = _render_for_console(frame, columns=columns, console=console)
    if console.is_terminal:
        terminal_width = max(console.size.width, 1)
        rendered_height = sum(
            max(1, (cast(Text, row).cell_len + terminal_width - 1) // terminal_width)
            for row in renderable.renderables
        )
        # Clear each previous row so a narrower replacement leaves no stale cells.
        console.control(
            Control.move_to_column(0),
            Control(
                *((ControlType.CURSOR_UP, 1), (ControlType.ERASE_IN_LINE, 2)) * rendered_height
            ),
        )
    console.print(renderable)


def animate_frames(
    frames: FrameSource,
    *,
    fps: float = DEFAULT_FPS,
    columns: int | None = None,
    repeat: bool = False,
    hold_final_seconds: float | None = None,
    console: Console | None = None,
    stop_event: Event | None = None,
    enabled: bool | None = None,
    alternate_screen: bool = False,
) -> None:
    """Render frames synchronously with optional repetition and cancellation."""
    if not is_playback_fps(fps):
        raise AnimationConfigError(
            "fps must be a positive finite number with a platform-supported frame interval."
        )
    if columns is not None and not is_valid_columns(columns):
        raise AnimationConfigError("columns must be a positive integer.")
    if hold_final_seconds is not None and not is_wait_duration(hold_final_seconds):
        raise AnimationConfigError(
            "hold_final_seconds must be a non-negative, platform-supported wait duration "
            "when provided."
        )
    if not is_bool(repeat):
        raise AnimationConfigError("repeat must be a boolean.")
    if enabled is not None and not is_bool(enabled):
        raise AnimationConfigError("enabled must be a boolean or None.")
    if not is_bool(alternate_screen):
        raise AnimationConfigError("alternate_screen must be a boolean.")
    if console is not None and not isinstance(console, Console):
        raise AnimationConfigError("console must be a rich Console or None.")

    console = Console() if console is None else console
    if enabled is None:
        enabled = bool(console.is_terminal)
    if not enabled:
        return
    stop_event = stop_event or Event()
    if stop_event.is_set():
        return

    frame_factory = (
        cast(Callable[[], Iterable[HMMFrame]] | None, frames) if callable(frames) else None
    )
    if frame_factory is not None:
        current_frames = _materialize_frames(frame_factory(), factory=True)
    else:
        current_frames = _materialize_frames(frames, factory=False)
    if stop_event.is_set():
        return

    frame_interval = 1 / fps
    final_hold_seconds = frame_interval if hold_final_seconds is None else hold_final_seconds
    refresh_rate = max(4, int(min(fps, 30) * 2))
    with Live(
        _render_for_console(current_frames[0], columns=columns, console=console),
        console=console,
        auto_refresh=False,
        refresh_per_second=refresh_rate,
        screen=alternate_screen,
    ) as live:
        keep_running = True
        initial_frame_rendered = True
        while keep_running and not stop_event.is_set():
            frame_index = 0
            while frame_index < len(current_frames):
                if stop_event.is_set():
                    break
                frame = current_frames[frame_index]
                if initial_frame_rendered:
                    initial_frame_rendered = False
                else:
                    live.update(
                        _render_for_console(frame, columns=columns, console=console),
                        refresh=True,
                    )
                hold_seconds = (
                    final_hold_seconds if frame_index == len(current_frames) - 1 else frame_interval
                )
                if hold_seconds > 0 and stop_event.wait(hold_seconds):
                    break
                frame_index += 1
            if stop_event.is_set():
                break
            keep_running = repeat
            if keep_running and frame_factory is not None:
                if stop_event.is_set():
                    break
                current_frames = _materialize_frames(frame_factory(), factory=True)
                if stop_event.is_set():
                    break
