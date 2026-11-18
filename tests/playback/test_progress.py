from __future__ import annotations

import re
import unittest
from io import StringIO
from queue import Queue
from threading import Event
from time import monotonic
from unittest.mock import patch

import pytest
from rich.console import Console

from anihmm import (
    AnimationConfigError,
    ProgressSession,
    SequenceError,
    SessionError,
    progress_animation,
)
from anihmm.playback import progress as progress_playback


@pytest.fixture(autouse=True)
def interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")


class ProgressSessionTests(unittest.TestCase):
    def test_work_advances_the_visible_scan_and_completed_path(self) -> None:
        console = Console(file=StringIO(), width=80)
        presented: Queue[tuple[list[str], set[str]]] = Queue()
        previous: tuple[list[str], set[str]] | None = None

        def record(renderable) -> None:
            nonlocal previous
            lines = []
            active = set()
            indices = {"D": 1, "I": 0, "M": 1}
            for segments in console.render_lines(renderable, pad=False):
                plain = "".join(segment.text for segment in segments)
                styles = [segment.style for segment in segments for _ in segment.text]
                lines.append(plain)
                for match in re.finditer(r"\(([SDIME])\)", plain):
                    kind = match[1]
                    node = kind
                    if kind in indices:
                        node += str(indices[kind])
                        indices[kind] += 1
                    style = styles[match.start() + 1]
                    if style is not None and style.bold:
                        active.add(node)
            snapshot = (lines, active)
            if snapshot != previous:
                presented.put(snapshot)
                previous = snapshot

        class RecordingLive:
            def __init__(self, renderable, **kwargs) -> None:
                record(renderable)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb) -> None:
                return None

            def update(self, renderable, **kwargs) -> None:
                record(renderable)

        def next_matching_frame(predicate):
            deadline = monotonic() + 1
            while True:
                remaining = deadline - monotonic()
                self.assertGreater(remaining, 0, "Expected frame was never presented")
                lines, active = presented.get(timeout=remaining)
                if predicate(lines, active):
                    return lines, active

        with patch.object(progress_playback, "Live", RecordingLive):
            with ProgressSession(
                columns=2, fps=1000, settle_seconds=0, enabled=True, console=console
            ) as session:
                self.assertEqual(presented.get(timeout=1)[1], {"S"})
                self.assertEqual(
                    [presented.get(timeout=1)[1] for _ in range(4)],
                    [{"S", "D1"}, {"S", "I0"}, {"S", "M1"}, {"S", "I0"}],
                )

                session.advance("M", emission="x")
                self.assertEqual(session.current_node, "M1")
                self.assertEqual(
                    next_matching_frame(lambda lines, active: "x" in lines[-1])[1], {"S", "M1"}
                )
                self.assertEqual(presented.get(timeout=1)[1], {"S", "M1", "D2"})

                session.advance("I", emission="y")
                self.assertEqual(
                    next_matching_frame(lambda lines, active: "y" in lines[-1])[1],
                    {"S", "M1", "I1"},
                )
                scans = [presented.get(timeout=1) for _ in range(4)]
                self.assertEqual(
                    [active for _lines, active in scans],
                    [
                        {"S", "M1", "I1", "D2"},
                        {"S", "M1", "I1"},
                        {"S", "M1", "I1", "M2"},
                        {"S", "M1", "I1"},
                    ],
                )
                self.assertIn("(I)<", scans[1][0][3])
                self.assertIn("(I)<", scans[3][0][3])

                session.advance("D")
                session.finish()
                self.assertEqual(session.current_node, "E")
                self.assertTrue(session.is_finished)
                lines, active = next_matching_frame(lambda lines, active: "E" in active)
                self.assertEqual(active, {"S", "M1", "I1", "D2", "E"})
                self.assertEqual(lines[-1].split(), ["x", "y"])

    def test_advance_validates_states_and_emissions_before_mutating(self) -> None:
        with ProgressSession(columns=3, enabled=False) as session:
            invalid_calls = (
                ("M", None),
                ("I", None),
                ("D", "A"),
                ("X", None),
            )
            for kind, emission in invalid_calls:
                with self.subTest(kind=kind, emission=emission):
                    with self.assertRaises(SequenceError):
                        session.advance(kind, emission=emission)
                    self.assertEqual(session.current_node, "S")

            session.advance("m", emission="A")
            session.advance("i", emission="C")
            session.advance("d")
            session.finish()

            self.assertEqual(session.current_node, "E")
            self.assertTrue(session.is_finished)
            with self.assertRaises(SessionError):
                session.advance("M", emission="G")

    def test_progress_configuration_and_lifecycle_are_validated(self) -> None:
        invalid_kwargs = (
            {"columns": 0},
            {"fps": 0},
            {"settle_seconds": -1},
            {"console": object()},
            {"enabled": 1},
            {"alternate_screen": None},
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(AnimationConfigError):
                    ProgressSession(**kwargs)  # type: ignore[arg-type]

        session = ProgressSession(enabled=False)
        with self.assertRaises(SessionError):
            session.advance("M", emission="A")
        session.start()
        with self.assertRaises(SessionError):
            session.start()
        session.stop()
        session.wait()
        with self.assertRaises(SessionError):
            session.advance("M", emission="A")

    def test_non_terminal_progress_remains_quiet(self) -> None:
        console = Console(file=StringIO(), force_terminal=False)
        with progress_animation(columns=2, console=console) as session:
            session.advance("M", emission="A")
            session.advance("D")
            session.finish()

        self.assertEqual(console.file.getvalue(), "")

    def test_context_manager_preserves_original_exception(self) -> None:
        failed = Event()

        class BrokenOutput(StringIO):
            def write(self, value: str) -> int:
                failed.set()
                raise OSError("terminal disconnected")

        console = Console(file=BrokenOutput(), force_terminal=True, force_interactive=True)
        with self.assertRaisesRegex(ValueError, "work failed"):
            with ProgressSession(console=console):
                self.assertTrue(failed.wait(1))
                raise ValueError("work failed")
