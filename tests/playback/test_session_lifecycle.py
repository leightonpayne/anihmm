from __future__ import annotations

import asyncio
import unittest
from io import StringIO
from threading import Event, Thread, Timer
from unittest.mock import patch

from rich.console import Console

from anihmm import (
    AnimationSession,
    AnimationTimeoutError,
    AsyncAnimationSession,
    HMMFrame,
    SessionError,
)
from anihmm.playback import session as playback_session


def _wait_for_session(session: AnimationSession, errors: list[BaseException]) -> None:
    try:
        session.wait()
    except BaseException as exc:
        errors.append(exc)


class SessionConcurrencyTests(unittest.TestCase):
    def test_timed_wait_is_not_blocked_by_another_waiter(self) -> None:
        join_entered = Event()
        release_work = Event()
        wait_errors: list[BaseException] = []

        class ObservedThread(Thread):
            def join(self, timeout=None) -> None:
                join_entered.set()
                super().join(timeout)

        def frames() -> list[HMMFrame]:
            release_work.wait(2.0)
            return [HMMFrame()]

        session = AnimationSession(
            frames,
            enabled=True,
            repeat=False,
            hold_final_seconds=0,
            console=Console(file=StringIO(), force_terminal=False),
        )
        with patch.object(playback_session, "Thread", ObservedThread):
            session.start()
            waiter = Thread(target=_wait_for_session, args=(session, wait_errors))
            rescue = Timer(1.0, release_work.set)
            waiter.start()
            rescue.start()
            try:
                self.assertTrue(join_entered.wait(1.0))
                with self.assertRaises(AnimationTimeoutError):
                    session.wait(timeout=0.01)
                self.assertTrue(session.is_running)
            finally:
                session.stop()
                release_work.set()
                waiter.join(1.0)
                rescue.cancel()
                rescue.join(1.0)
                session.wait(timeout=1.0)
        self.assertEqual(wait_errors, [])

    def test_old_waiter_cannot_clear_a_running_replacement(self) -> None:
        self._assert_old_waiter_preserves_replacement(replacement_fails=False)

    def test_old_waiter_cannot_consume_a_replacement_error(self) -> None:
        self._assert_old_waiter_preserves_replacement(replacement_fails=True)

    def _assert_old_waiter_preserves_replacement(self, *, replacement_fails: bool) -> None:
        old_join_entered = Event()
        release_old_join = Event()
        replacement_started = Event()
        release_work = Event()
        workers: list[Thread] = []
        wait_errors: list[BaseException] = []
        runs = 0

        class ControlledThread(Thread):
            def join(self, timeout=None) -> None:
                super().join(timeout)
                if self is workers[0]:
                    old_join_entered.set()
                    release_old_join.wait(2.0)

        def worker_thread(**kwargs) -> Thread:
            worker = ControlledThread(**kwargs)
            workers.append(worker)
            return worker

        def frames() -> list[HMMFrame]:
            nonlocal runs
            runs += 1
            if runs == 2:
                replacement_started.set()
                if replacement_fails:
                    raise ValueError("replacement failed")
                release_work.wait(2.0)
            return [HMMFrame()]

        session = AnimationSession(
            frames,
            enabled=True,
            repeat=False,
            hold_final_seconds=0,
            console=Console(file=StringIO(), force_terminal=False),
        )
        with patch.object(playback_session, "Thread", side_effect=worker_thread):
            session.start()
            # Finish the worker without consuming its result through session.wait().
            Thread.join(workers[0], 1.0)
            self.assertFalse(session.is_running)
            waiter = Thread(target=_wait_for_session, args=(session, wait_errors))
            waiter.start()
            try:
                self.assertTrue(old_join_entered.wait(1.0))
                session.start()
                self.assertTrue(replacement_started.wait(1.0))
                if replacement_fails:
                    Thread.join(workers[1], 1.0)
                release_old_join.set()
                waiter.join(1.0)
                self.assertFalse(waiter.is_alive())
                self.assertEqual(wait_errors, [])
                if replacement_fails:
                    with self.assertRaises(SessionError) as caught:
                        session.wait(timeout=1.0)
                    self.assertIsInstance(caught.exception.__cause__, ValueError)
                    self.assertEqual(str(caught.exception.__cause__), "replacement failed")
                else:
                    self.assertTrue(session.is_running)
            finally:
                release_old_join.set()
                session.stop()
                release_work.set()
                waiter.join(1.0)
                for worker in workers:
                    Thread.join(worker, 1.0)
                session.wait(timeout=1.0)


class AsyncSessionConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_rejects_running_session_while_async_wait_is_pending(self) -> None:
        join_entered = Event()
        release_work = Event()
        rescued = Event()

        class ObservedThread(Thread):
            def join(self, timeout=None) -> None:
                join_entered.set()
                super().join(timeout)

        def frames() -> list[HMMFrame]:
            release_work.wait(2.0)
            return [HMMFrame()]

        session = AsyncAnimationSession(
            frames,
            enabled=True,
            repeat=False,
            hold_final_seconds=0,
            console=Console(file=StringIO(), force_terminal=False),
        )

        def rescue_loop() -> None:
            rescued.set()
            session.stop()
            release_work.set()

        with patch.object(playback_session, "Thread", ObservedThread):
            await session.start()
            waiter = asyncio.create_task(session.wait())
            rescue = Timer(1.0, rescue_loop)
            rescue.start()
            try:
                self.assertTrue(await asyncio.to_thread(join_entered.wait, 1.0))
                with self.assertRaises(SessionError):
                    await session.start()
                self.assertFalse(rescued.is_set())
                self.assertTrue(session.is_running)
            finally:
                session.stop()
                release_work.set()
                await session.wait(timeout=1.0)
                await waiter
                rescue.cancel()
                rescue.join(1.0)
