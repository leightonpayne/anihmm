"""Validated playback and preset selection options."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from rich.console import Console

from anihmm._symbols import normalize_terminal_symbol
from anihmm._validation import is_bool, is_playback_fps, is_valid_columns, is_wait_duration
from anihmm.exceptions import AnimationConfigError
from anihmm.models import FrameSource, HMMFrame
from anihmm.presets import DEMO_COLUMNS, build_demo_frames, build_random_frames

DEFAULT_FPS = 12.0


@dataclass(frozen=True, slots=True)
class PlaybackOptions:
    """Runtime playback configuration."""

    fps: float = DEFAULT_FPS
    columns: int | None = None
    repeat: bool = False
    hold_final_seconds: float | None = None
    console: Console | None = None
    enabled: bool | None = None
    alternate_screen: bool = False

    def __post_init__(self) -> None:
        """Validate playback configuration."""
        if not is_playback_fps(self.fps):
            raise AnimationConfigError(
                "fps must be a positive finite number with a platform-supported frame interval."
            )
        if self.columns is not None and not is_valid_columns(self.columns):
            raise AnimationConfigError("columns must be a positive integer when provided.")
        if self.hold_final_seconds is not None and not is_wait_duration(self.hold_final_seconds):
            raise AnimationConfigError(
                "hold_final_seconds must be a non-negative, platform-supported wait duration "
                "when provided."
            )
        if self.console is not None and not isinstance(self.console, Console):
            raise AnimationConfigError("console must be a rich Console or None.")
        if not is_bool(self.repeat):
            raise AnimationConfigError("repeat must be a boolean.")
        if self.enabled is not None and not is_bool(self.enabled):
            raise AnimationConfigError("enabled must be a boolean or None.")
        if not is_bool(self.alternate_screen):
            raise AnimationConfigError("alternate_screen must be a boolean.")

    @classmethod
    def background(
        cls,
        *,
        fps: float = DEFAULT_FPS,
        hold_final_seconds: float | None = None,
        console: Console | None = None,
        enabled: bool | None = None,
        alternate_screen: bool = False,
    ) -> PlaybackOptions:
        """Build options for looping background playback sessions."""
        return cls(
            fps=fps,
            columns=None,
            repeat=True,
            hold_final_seconds=hold_final_seconds,
            console=console,
            enabled=enabled,
            alternate_screen=alternate_screen,
        )


@dataclass(frozen=True, slots=True)
class ProcessingOptions:
    """Preset selection for looping background animations."""

    columns: int = DEMO_COLUMNS
    random_path: bool = False
    seed: int | None = None
    emissions: int | str | None = None

    def __post_init__(self) -> None:
        """Validate preset configuration."""
        if not is_valid_columns(self.columns):
            raise AnimationConfigError("columns must be a positive integer.")
        if not is_bool(self.random_path):
            raise AnimationConfigError("random_path must be a boolean.")
        if self.seed is not None and type(self.seed) is not int:
            raise AnimationConfigError("seed must be an integer or None.")
        if self.emissions is not None and type(self.emissions) not in {int, str}:
            raise AnimationConfigError("emissions must be an integer count, a string, or None.")
        if type(self.emissions) is int and self.emissions < 0:
            raise AnimationConfigError("emissions must be >= 0 when provided as a count.")
        if isinstance(self.emissions, str):
            invalid_symbol = next(
                (symbol for symbol in self.emissions if normalize_terminal_symbol(symbol) is None),
                None,
            )
            if invalid_symbol is not None:
                raise AnimationConfigError(
                    "Each emission must be a non-whitespace symbol occupying one terminal cell; "
                    f"got {invalid_symbol!r}."
                )
        if self.random_path and self.emissions is not None:
            emission_count = (
                len(self.emissions) if isinstance(self.emissions, str) else self.emissions
            )
            maximum = 2 * self.columns + 1
            if emission_count > maximum:
                raise AnimationConfigError(
                    f"A {self.columns}-column random path supports at most {maximum} emissions; "
                    f"got {emission_count}."
                )

    @classmethod
    def random(
        cls,
        *,
        columns: int = DEMO_COLUMNS,
        seed: int | None = None,
        emissions: int | str | None = None,
    ) -> ProcessingOptions:
        """Build a random-path preset selection."""
        return cls(columns=columns, random_path=True, seed=seed, emissions=emissions)

    @classmethod
    def demo(cls, *, columns: int = DEMO_COLUMNS) -> ProcessingOptions:
        """Build the default demo preset selection."""
        return cls(columns=columns)

    def frame_source(self) -> FrameSource:
        """Build a reusable frame source for playback sessions."""
        if self.random_path:
            random_seed = self.seed
            seed_lock = Lock()

            def frames() -> list[HMMFrame]:
                nonlocal random_seed
                with seed_lock:
                    current_seed = random_seed
                    if random_seed is not None:
                        random_seed += 1
                return build_random_frames(
                    columns=self.columns,
                    seed=current_seed,
                    emissions=self.emissions,
                )

            return frames

        def frames() -> list[HMMFrame]:
            return build_demo_frames(columns=self.columns)

        return frames
