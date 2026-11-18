from __future__ import annotations

import asyncio
import unittest
from io import StringIO
from threading import TIMEOUT_MAX, Event
from time import monotonic

import pytest
from rich.console import Console

from anihmm import (
    AnimationConfigError,
    AnimationSession,
    AnimationTimeoutError,
    AsyncAnimationSession,
    HMMFrame,
    PlaybackOptions,
    ProcessingOptions,
    SessionError,
    animate_frames,
    async_processing_animation,
    print_frame_in_place,
    processing_animation,
)


@pytest.fixture(autouse=True)
def interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")


class PlaybackContractTests(unittest.TestCase):
    def test_animate_frames_rejects_invalid_config(self) -> None:
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], fps=0, enabled=True)
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], columns=0, enabled=True)
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], hold_final_seconds=-1, enabled=True)
        with self.assertRaises(AnimationConfigError):
            animate_frames([], enabled=True)

    def test_rendering_helpers_reject_invalid_console_objects(self) -> None:
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], console=object(), enabled=True)  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            print_frame_in_place(HMMFrame(), console=object())  # type: ignore[arg-type]

    def test_animate_frames_rejects_malformed_frame_sources(self) -> None:
        with self.assertRaises(AnimationConfigError):
            animate_frames(["not-a-frame"], enabled=True)  # type: ignore[list-item]
        with self.assertRaises(AnimationConfigError):
            animate_frames(lambda: None, enabled=True)  # type: ignore[arg-type,return-value]
        with self.assertRaises(AnimationConfigError):
            animate_frames(lambda: [], enabled=True)

    def test_animate_frames_accepts_one_shot_iterables(self) -> None:
        console = Console(file=StringIO(), force_terminal=True, record=True)
        frames = (frame for frame in [HMMFrame(columns=1, emissions=["M1:x"])])

        animate_frames(frames, console=console, hold_final_seconds=0)

        self.assertIn("x", console.export_text())

    def test_animate_frames_preserves_type_errors_raised_during_iteration(self) -> None:
        def broken_frames():
            yield HMMFrame()
            raise TypeError("generator implementation bug")

        with self.assertRaisesRegex(TypeError, "generator implementation bug"):
            animate_frames(broken_frames(), enabled=True)

    def test_disabled_playback_is_quiet_and_does_not_consume_the_source(self) -> None:
        def frame_factory():
            raise AssertionError("Disabled playback must not consume the frame source")

        for terminal, enabled in ((False, None), (True, False)):
            with self.subTest(terminal=terminal, enabled=enabled):
                output = StringIO()
                console = Console(file=output, force_terminal=terminal)
                animate_frames(frame_factory, console=console, enabled=enabled)
                self.assertEqual(output.getvalue(), "")

    def test_cancellation_during_frame_generation_leaves_output_untouched(self) -> None:
        stop_event = Event()
        output = StringIO()

        def frame_factory() -> list[HMMFrame]:
            stop_event.set()
            return [HMMFrame(active_nodes={"S"})]

        animate_frames(
            frame_factory,
            console=Console(file=output, force_terminal=True),
            stop_event=stop_event,
        )

        self.assertEqual(output.getvalue(), "")

    def test_repeat_renders_fresh_frames_until_the_factory_cancels(self) -> None:
        symbols = iter("xyz")
        stop_event = Event()
        console = Console(file=StringIO(), force_terminal=True, record=True)

        def frame_factory() -> list[HMMFrame]:
            symbol = next(symbols)
            if symbol == "z":
                stop_event.set()
            return [HMMFrame(columns=1, emissions=[f"M1:{symbol}"])]

        animate_frames(
            frame_factory,
            console=console,
            repeat=True,
            hold_final_seconds=0,
            stop_event=stop_event,
        )

        output = console.export_text()
        self.assertIn("x", output)
        self.assertIn("y", output)
        self.assertNotIn("z", output)

    def test_cancelled_playback_is_quiet_and_does_not_consume_the_source(self) -> None:
        output = StringIO()
        stop_event = Event()
        stop_event.set()

        def frame_factory():
            raise AssertionError("Cancelled playback must not consume the frame source")

        animate_frames(
            frame_factory,
            console=Console(file=output, force_terminal=True),
            stop_event=stop_event,
        )

        self.assertEqual(output.getvalue(), "")

    def test_options_validate_at_construction_time(self) -> None:
        for fps in (0, float("nan"), float("inf"), True):
            with self.subTest(fps=fps):
                with self.assertRaises(AnimationConfigError):
                    PlaybackOptions(fps=fps)
        for columns in (0, 1.5, True):
            with self.subTest(columns=columns):
                with self.assertRaises(AnimationConfigError):
                    PlaybackOptions(columns=columns)  # type: ignore[arg-type]
                with self.assertRaises(AnimationConfigError):
                    ProcessingOptions(columns=columns)  # type: ignore[arg-type]
        for hold in (-1, float("nan"), float("inf")):
            with self.subTest(hold=hold):
                with self.assertRaises(AnimationConfigError):
                    PlaybackOptions(hold_final_seconds=hold)
        for seed in (True, 1.5, "seed", b"seed", []):
            with self.subTest(seed=seed):
                with self.assertRaises(AnimationConfigError):
                    ProcessingOptions.random(seed=seed)  # type: ignore[arg-type]
        for emissions in (-1, True, 1.5):
            with self.subTest(emissions=emissions):
                with self.assertRaises(AnimationConfigError):
                    ProcessingOptions.random(emissions=emissions)  # type: ignore[arg-type]
        for kwargs in (
            {"repeat": "false"},
            {"enabled": 1},
            {"alternate_screen": None},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(AnimationConfigError):
                    PlaybackOptions(**kwargs)  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            ProcessingOptions(random_path="false")  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            ProcessingOptions.random(emissions="界")
        with self.assertRaises(AnimationConfigError):
            PlaybackOptions(console=object())  # type: ignore[arg-type]
        for emissions in (6, "SEARCH"):
            with self.subTest(impossible_emissions=emissions):
                with self.assertRaises(AnimationConfigError):
                    ProcessingOptions.random(columns=2, emissions=emissions)

        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], repeat="false", enabled=True)  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], enabled=1)  # type: ignore[arg-type]

    def test_timing_values_must_fit_platform_threading_waits(self) -> None:
        too_long = TIMEOUT_MAX * 2
        tiny_fps = 5e-324

        for options_factory in (
            lambda: PlaybackOptions(fps=tiny_fps),
            lambda: PlaybackOptions(hold_final_seconds=too_long),
        ):
            with self.subTest(options_factory=options_factory):
                with self.assertRaises(AnimationConfigError):
                    options_factory()

        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], fps=tiny_fps, enabled=True)
        with self.assertRaises(AnimationConfigError):
            animate_frames([HMMFrame()], hold_final_seconds=too_long, enabled=True)

    def test_alternate_screen_is_opt_in_and_restored_after_playback(self) -> None:
        for alternate_screen in (False, True):
            with self.subTest(alternate_screen=alternate_screen):
                output = StringIO()
                console = Console(file=output, force_terminal=True, legacy_windows=False)
                animate_frames(
                    [HMMFrame()],
                    console=console,
                    hold_final_seconds=0,
                    alternate_screen=alternate_screen,
                )
                self.assertEqual("\x1b[?1049h" in output.getvalue(), alternate_screen)
                self.assertEqual("\x1b[?1049l" in output.getvalue(), alternate_screen)

    def test_frame_timing_and_final_hold(self) -> None:
        class ClockEvent:
            def __init__(self, console: Console) -> None:
                self.console = console
                self.elapsed = 0.0
                self.presented: dict[str, float] = {}

            def is_set(self) -> bool:
                return False

            def wait(self, seconds: float) -> bool:
                output = self.console.export_text()
                for symbol in "xy":
                    if symbol in output:
                        self.presented.setdefault(symbol, self.elapsed)
                self.elapsed += seconds
                return False

        for final_hold, expected_duration in ((None, 0.25), (0.5, 0.625)):
            with self.subTest(final_hold=final_hold):
                console = Console(file=StringIO(), force_terminal=True, record=True)
                clock = ClockEvent(console)
                animate_frames(
                    [
                        HMMFrame(columns=1, emissions=["M1:x"]),
                        HMMFrame(columns=1, emissions=["M1:y"]),
                    ],
                    fps=8,
                    hold_final_seconds=final_hold,
                    stop_event=clock,
                    console=console,
                )
                self.assertAlmostEqual(clock.elapsed, expected_duration)
                self.assertEqual(set(clock.presented), {"x", "y"})
                self.assertAlmostEqual(clock.presented["x"], 0.0)
                self.assertAlmostEqual(clock.presented["y"], 0.125)


class SessionContractTests(unittest.TestCase):
    def test_animation_session_replays_one_shot_frame_iterables(self) -> None:
        console = Console(file=StringIO(), force_terminal=True, record=True)
        frames = (frame for frame in [HMMFrame(columns=1, emissions=["M1:x"])])
        session = AnimationSession(
            frames,
            repeat=False,
            hold_final_seconds=0,
            console=console,
        )

        for _ in range(2):
            session.start()
            session.wait(timeout=1)
            self.assertIn("x", console.export_text())

    def test_sessions_and_helpers_reject_invalid_option_objects_early(self) -> None:
        frames = [HMMFrame()]
        with self.assertRaises(AnimationConfigError):
            AnimationSession(frames, options=object())  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            AsyncAnimationSession(frames, options=object())  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            processing_animation(processing=0)  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            processing_animation(playback=object())  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            async_processing_animation(processing=object())  # type: ignore[arg-type]
        with self.assertRaises(AnimationConfigError):
            async_processing_animation(playback=object())  # type: ignore[arg-type]

    def test_session_preserves_frame_column_count_by_default(self) -> None:
        console = Console(file=StringIO(), force_terminal=True, width=100, record=True)
        session = AnimationSession(
            [HMMFrame(columns=8, emissions=["M8:x"])],
            repeat=False,
            hold_final_seconds=0,
            console=console,
        )
        session.start()
        session.wait(timeout=1)

        output = console.export_text()
        self.assertIn("x", output)
        self.assertTrue(any(line.count("M") == 8 for line in output.splitlines()))

    def test_animation_session_start_stop_and_timeout(self) -> None:
        session = AnimationSession(
            [HMMFrame()],
            console=Console(file=StringIO(), force_terminal=True),
            hold_final_seconds=60,
        ).start()
        try:
            self.assertTrue(session.is_running)
            with self.assertRaises(AnimationTimeoutError):
                session.wait(timeout=0.01)
        finally:
            session.stop()
            session.wait(timeout=1)

        self.assertFalse(session.is_running)

    def test_animation_session_surfaces_worker_errors(self) -> None:
        failure = ValueError("frame generation failed")

        def frames():
            raise failure

        session = AnimationSession(frames, enabled=True).start()
        with self.assertRaises(SessionError) as raised:
            session.wait(timeout=1)
        self.assertIs(raised.exception.__cause__, failure)

    def test_animation_session_validates_timeout_and_preserves_unobserved_errors(self) -> None:
        failure = ValueError("frame generation failed")
        calls = 0

        def frames():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise failure
            return [HMMFrame()]

        session = AnimationSession(
            frames,
            console=Console(file=StringIO(), force_terminal=True),
            repeat=False,
            hold_final_seconds=0,
        )
        for timeout in (-1, float("nan"), float("inf"), True, TIMEOUT_MAX * 2):
            with self.subTest(timeout=timeout):
                with self.assertRaises(AnimationConfigError):
                    session.wait(timeout=timeout)

        session.start()
        deadline = monotonic() + 1
        while session.is_running and monotonic() < deadline:
            Event().wait(0.001)
        self.assertFalse(session.is_running)
        with self.assertRaises(SessionError) as raised:
            session.start()
        self.assertIs(raised.exception.__cause__, failure)

        session.start()
        session.wait(timeout=1)
        self.assertFalse(session.is_running)

    def test_processing_options_reproduce_a_series_of_changing_paths(self) -> None:
        options = ProcessingOptions.random(columns=6, seed=7, emissions="SEARCHING")
        source = options.frame_source()
        runs = [list(source()) for _ in range(8)]

        replay = options.frame_source()
        self.assertEqual(runs, [list(replay()) for _ in range(8)])
        self.assertGreater(len({frozenset(frames[-1].active_nodes) for frames in runs}), 1)
        for frames in runs:
            self.assertEqual(frames[-1].columns, 6)
            self.assertEqual(
                "".join(emission.split(":", 1)[1] for emission in frames[-1].emissions),
                "SEARCHING",
            )

    def test_processing_animation_uses_the_demo_when_no_preset_is_selected(self) -> None:
        console = Console(file=StringIO(), force_terminal=True, record=True)
        with processing_animation(
            playback=PlaybackOptions(fps=1000, repeat=False, hold_final_seconds=0, console=console)
        ) as session:
            session.wait(timeout=1)

        labels = ["".join(line.split()) for line in console.export_text().splitlines()]
        self.assertIn("SEARCHING", labels)

    def test_context_manager_preserves_original_exception(self) -> None:
        started = Event()

        def frames():
            started.set()
            raise RuntimeError("worker failed")

        with self.assertRaisesRegex(ValueError, "work failed"):
            with AnimationSession(frames, enabled=True):
                self.assertTrue(started.wait(1))
                raise ValueError("work failed")


class AsyncSessionContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_session_preserves_frame_column_count_by_default(self) -> None:
        console = Console(file=StringIO(), force_terminal=True, width=100, record=True)
        session = AsyncAnimationSession(
            [HMMFrame(columns=8, emissions=["M8:x"])],
            repeat=False,
            hold_final_seconds=0,
            console=console,
        )
        await session.start()
        await session.wait(timeout=1)

        output = console.export_text()
        self.assertIn("x", output)
        self.assertTrue(any(line.count("M") == 8 for line in output.splitlines()))

    async def test_async_session_wait_and_timeout(self) -> None:
        session = AsyncAnimationSession(
            [HMMFrame()],
            console=Console(file=StringIO(), force_terminal=True),
            hold_final_seconds=60,
        )
        await session.start()
        try:
            with self.assertRaises(AnimationTimeoutError):
                await session.wait(timeout=0.01)
        finally:
            session.stop()
            await session.wait(timeout=1)
        self.assertFalse(session.is_running)

    async def test_async_session_rejects_negative_timeout(self) -> None:
        session = AsyncAnimationSession([HMMFrame()], repeat=False)
        with self.assertRaises(AnimationConfigError):
            await session.wait(timeout=-1)

    async def test_async_processing_animation_renders_and_stops_on_context_exit(self) -> None:
        presented = Event()

        class ObservedOutput(StringIO):
            def write(self, value: str) -> int:
                if "x" in value:
                    presented.set()
                return super().write(value)

        console = Console(file=ObservedOutput(), force_terminal=True)
        async with async_processing_animation(
            ProcessingOptions.random(columns=1, emissions="x", seed=7),
            PlaybackOptions.background(fps=1000, hold_final_seconds=0, console=console),
        ) as session:
            self.assertTrue(await asyncio.to_thread(presented.wait, 1))
            self.assertTrue(session.is_running)

        self.assertFalse(session.is_running)

    async def test_async_context_manager_preserves_original_exception(self) -> None:
        started = Event()

        def frames():
            started.set()
            raise RuntimeError("worker failed")

        with self.assertRaisesRegex(ValueError, "work failed"):
            async with AsyncAnimationSession(frames, enabled=True):
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                raise ValueError("work failed")
