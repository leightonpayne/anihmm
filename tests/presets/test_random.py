from __future__ import annotations

import unittest

from anihmm import AnimationConfigError, HMMFrame, SequenceError
from anihmm.presets import (
    build_demo_frames,
    build_random_frames,
    build_random_path_frame,
    build_random_steps,
    extend_frames,
)


class RandomSequenceTests(unittest.TestCase):
    def test_demo_is_deterministic_and_supports_small_lattices(self) -> None:
        frames = build_demo_frames()
        self.assertEqual(frames, build_demo_frames())
        self.assertEqual(frames[0].active_nodes, {"S"})
        self.assertEqual(
            "".join(emission.split(":", 1)[1] for emission in frames[-1].emissions),
            "SEARCHING",
        )

        for columns, label in ((1, "SEA"), (2, "SEARC"), (3, "SEARCHI")):
            with self.subTest(columns=columns):
                frames = build_demo_frames(columns=columns)
                self.assertEqual(frames[-1].columns, columns)
                self.assertIn("E", frames[-1].active_nodes)
                self.assertEqual(
                    "".join(emission.split(":", 1)[1] for emission in frames[-1].emissions),
                    label,
                )

        for columns in (None, "5", 1.5, True, 0):
            with self.subTest(invalid_columns=columns):
                with self.assertRaises(SequenceError):
                    build_demo_frames(columns=columns)  # type: ignore[arg-type]

    def test_random_frames_start_at_s_and_end_at_e(self) -> None:
        frames = build_random_frames(columns=5, seed=3)

        self.assertEqual(frames[0].active_nodes, {"S"})
        self.assertIn("E", frames[-1].active_nodes)

    def test_extend_frames_preserves_its_frame_contract(self) -> None:
        first = HMMFrame()
        second = HMMFrame(active_nodes={"S"})
        self.assertEqual(extend_frames((frame for frame in [first]), second), [first, second])

        with self.assertRaisesRegex(AnimationConfigError, "existing must be an iterable"):
            extend_frames(None)  # type: ignore[arg-type]
        with self.assertRaisesRegex(AnimationConfigError, "combined frame index 0"):
            extend_frames(["bad"])  # type: ignore[list-item]
        with self.assertRaisesRegex(AnimationConfigError, "combined frame index 1"):
            extend_frames([first], "bad")  # type: ignore[arg-type]

    def test_random_sequence_is_deterministic_for_seed(self) -> None:
        steps_a = build_random_steps(columns=5, seed=7)
        steps_b = build_random_steps(columns=5, seed=7)

        self.assertEqual(steps_a, steps_b)

    def test_random_sequence_emits_amino_acids_only_on_i_or_m(self) -> None:
        steps = build_random_steps(columns=5, seed=11)

        for step in steps:
            for emission in step.emissions:
                anchor, symbol = emission.split(":", 1)
                self.assertIn(anchor[0], {"I", "M"})
                self.assertIn(symbol, "ACDEFGHIKLMNPQRSTVWY")

    def test_random_frames_can_target_exact_emission_count(self) -> None:
        frames = build_random_frames(columns=5, seed=7, emissions=4)

        self.assertEqual(len(frames[-1].emissions), 4)

    def test_random_frames_can_target_exact_emission_symbols_in_order(self) -> None:
        frames = build_random_frames(columns=10, seed=7, emissions="WORKING")

        self.assertEqual(
            "".join(emission.split(":", 1)[1] for emission in frames[-1].emissions), "WORKING"
        )

    def test_random_path_frame_returns_final_settled_frame(self) -> None:
        frame = build_random_path_frame(columns=10, seed=7, emissions="COMPLETE")

        self.assertIn("E", frame.active_nodes)
        self.assertEqual(
            "".join(emission.split(":", 1)[1] for emission in frame.emissions),
            "COMPLETE",
        )

    def test_random_sequence_rejects_impossible_emissions(self) -> None:
        for emissions in (6, "SEARCHING"):
            with self.subTest(emissions=emissions):
                with self.assertRaises(SequenceError):
                    build_random_steps(columns=2, seed=7, emissions=emissions)

    def test_random_sequence_rejects_invalid_emission_spec_types(self) -> None:
        for emissions in (True, 1.5, "界", "A B"):
            with self.subTest(emissions=emissions):
                with self.assertRaises(SequenceError):
                    build_random_steps(emissions=emissions)  # type: ignore[arg-type]

    def test_random_sequence_rejects_invalid_seed_types(self) -> None:
        for seed in (True, 1.5, "seed", b"seed", []):
            with self.subTest(seed=seed):
                with self.assertRaises(SequenceError):
                    build_random_steps(seed=seed)  # type: ignore[arg-type]

    def test_exact_emission_planning_handles_large_lattices(self) -> None:
        steps = build_random_steps(columns=1000, seed=7, emissions=1)
        self.assertEqual(len(steps[-1].emissions), 1)
        self.assertEqual(steps[-1].committed[-1][1], "E")
