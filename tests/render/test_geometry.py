from __future__ import annotations

import unittest

from anihmm import (
    HMMSequence,
    InvalidTransitionError,
    compile_steps,
)
from anihmm.render import flash_overlay_cells, transition_cells


class FinishTransitionTests(unittest.TestCase):
    def test_geometry_rejects_non_string_node_identifiers(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            transition_cells(2, [], "M1")  # type: ignore[arg-type]
        with self.assertRaises(InvalidTransitionError):
            flash_overlay_cells(2, [])  # type: ignore[arg-type]

    def test_geometry_rejects_insertion_to_insertion_transitions(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            transition_cells(2, "I0", "I1")

    def test_geometry_rejects_invalid_column_count(self) -> None:
        for columns in (0, 1.5, True):
            with self.subTest(columns=columns):
                with self.assertRaises(InvalidTransitionError):
                    transition_cells(columns, "S", "M1")  # type: ignore[arg-type]
                with self.assertRaises(InvalidTransitionError):
                    flash_overlay_cells(columns, "S")  # type: ignore[arg-type]

    def test_final_deletion_can_transition_to_insertion(self) -> None:
        self.assertEqual(transition_cells(5, "D5", "I5"), {(1, 35), (2, 36)})

    def test_finish_from_m5_compiles_m5_to_e_path(self) -> None:
        sequence = HMMSequence(start="M5")
        sequence.emit("A")
        sequence.finish()

        frame = compile_steps(sequence.build())[-1]
        self.assertEqual(
            frame.active_cells,
            {(6, 36), (6, 37), (6, 38), (6, 39), (6, 40), (4, 42), (5, 41)},
        )
        self.assertIn("E", frame.active_nodes)

    def test_finish_from_i5_compiles_i5_to_e_path(self) -> None:
        sequence = HMMSequence(start="I5")
        sequence.emit("C")
        sequence.finish()

        frame = compile_steps(sequence.build())[-1]
        self.assertEqual(frame.active_cells, {(3, 39), (3, 40), (3, 41)})
        self.assertIn("E", frame.active_nodes)

    def test_finish_from_d5_compiles_d5_to_e_path(self) -> None:
        sequence = HMMSequence(start="D5")
        sequence.finish()

        frame = compile_steps(sequence.build())[-1]
        self.assertEqual(
            frame.active_cells,
            {(0, 36), (0, 37), (0, 38), (0, 39), (0, 40), (1, 41), (2, 42)},
        )
        self.assertIn("E", frame.active_nodes)

    def test_finish_fills_remaining_columns_with_deletions(self) -> None:
        sequence = HMMSequence(columns=5)
        sequence.settle("M")
        sequence.emit("A")
        sequence.finish()

        self.assertEqual(
            sequence.committed,
            [
                ("S", "M1"),
                ("M1", "D2"),
                ("D2", "D3"),
                ("D3", "D4"),
                ("D4", "D5"),
                ("D5", "E"),
            ],
        )
        frames = compile_steps(sequence.build(), columns=5)
        self.assertEqual(frames[-1].active_nodes, {"S", "M1", "D2", "D3", "D4", "D5", "E"})

    def test_d_to_m_transition_is_supported(self) -> None:
        sequence = HMMSequence(start="D2")
        sequence.settle("M")
        sequence.emit("C")

        frame = compile_steps(sequence.build())[-1]
        self.assertEqual(
            frame.active_cells,
            {(1, 16), (2, 16), (3, 16), (4, 17), (5, 18), (6, 19), (6, 20)},
        )
        self.assertIn("M3", frame.active_nodes)

    def test_m_to_d_transition_matches_reference_shape(self) -> None:
        self.assertEqual(
            transition_cells(5, "M1", "D2"),
            {(3, 10), (4, 10), (5, 10), (1, 12), (2, 11), (0, 13), (0, 14)},
        )
