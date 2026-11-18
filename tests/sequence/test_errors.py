from __future__ import annotations

import unittest

from anihmm import (
    FrameCompilationError,
    HMMSequence,
    InvalidTransitionError,
    SequenceError,
    compile_steps,
)
from anihmm.models import Step
from anihmm.sequence import compile_step


class SequenceValidationTests(unittest.TestCase):
    def test_sequence_rejects_non_string_actions(self) -> None:
        with self.assertRaises(SequenceError):
            HMMSequence(start=1)  # type: ignore[arg-type]

        sequence = HMMSequence()
        with self.assertRaises(SequenceError):
            sequence.settle(1)  # type: ignore[arg-type]
        sequence.settle("M")
        with self.assertRaises(SequenceError):
            sequence.emit(1)  # type: ignore[arg-type]

    def test_sequence_rejects_non_string_titles_before_mutation(self) -> None:
        sequence = HMMSequence()
        with self.assertRaises(SequenceError):
            sequence.cycle("M", title=1)  # type: ignore[arg-type]
        with self.assertRaises(SequenceError):
            sequence.settle("M", title=1)  # type: ignore[arg-type]
        self.assertEqual(sequence.build(), [])

        sequence.settle("M", title="Start")
        with self.assertRaises(SequenceError):
            sequence.emit("A", title=1)  # type: ignore[arg-type]
        sequence.emit("A", title="Label")
        with self.assertRaises(SequenceError):
            sequence.flash_current(title=1)  # type: ignore[arg-type]
        with self.assertRaises(SequenceError):
            sequence.finish(title=1)  # type: ignore[arg-type]
        self.assertEqual(
            sequence.build(),
            [
                Step("Start", committed=(("S", "M1"),)),
                Step("Label", committed=(("S", "M1"),), emissions=("M1:A",)),
            ],
        )

    def test_sequence_rejects_invalid_start_nodes(self) -> None:
        for start in ("", "Q1", "M0", "D0", "M6", "M01", "I00", "M²", "M١"):
            with self.subTest(start=start):
                with self.assertRaises(SequenceError):
                    HMMSequence(start=start, columns=5)

    def test_sequence_rejects_moves_beyond_the_last_column(self) -> None:
        sequence = HMMSequence(columns=5)
        for _ in range(5):
            sequence.settle("M")
            sequence.emit("A")

        with self.assertRaises(InvalidTransitionError):
            sequence.cycle("D")

    def test_sequence_rejects_direct_insertion_revisits(self) -> None:
        sequence = HMMSequence()
        sequence.settle("M")
        sequence.emit("A")
        sequence.settle("I")
        sequence.emit("C")

        with self.assertRaises(SequenceError):
            sequence.cycle("I")

    def test_emit_requires_exactly_one_non_whitespace_symbol(self) -> None:
        for symbol in ("", " ", "AB", "界", "🧬"):
            with self.subTest(symbol=symbol):
                sequence = HMMSequence()
                sequence.settle("M")

                with self.assertRaises(SequenceError):
                    sequence.emit(symbol)

    def test_emit_rejects_non_emitting_states(self) -> None:
        for current_node in ("S", "D1", "E"):
            with self.subTest(current_node=current_node):
                sequence = HMMSequence(start=current_node)

                with self.assertRaises(SequenceError):
                    sequence.emit("A")

    def test_modifying_returned_state_does_not_change_the_sequence(self) -> None:
        sequence = HMMSequence(columns=2)
        sequence.settle("M")
        sequence.emit("A")

        sequence.steps.clear()
        sequence.committed.append(("M1", "Missing"))
        sequence.emissions.append("Missing:A")

        self.assertEqual(
            [(step.committed, step.emissions) for step in sequence.build()],
            [((("S", "M1"),), ()), ((("S", "M1"),), ("M1:A",))],
        )
        sequence.settle("D")
        self.assertEqual(sequence.build()[-1].committed, (("S", "M1"), ("M1", "D2")))
        self.assertEqual(sequence.build()[-1].emissions, ("M1:A",))

    def test_emit_rejects_a_second_emission_from_the_same_node(self) -> None:
        sequence = HMMSequence()
        sequence.settle("M")
        sequence.emit("A")

        with self.assertRaises(SequenceError):
            sequence.emit("B")

    def test_emitting_states_require_an_emission_before_progress(self) -> None:
        for state, node in (("M", "M1"), ("I", "I0")):
            for action in ("cycle", "settle", "finish", "build"):
                with self.subTest(state=state, action=action):
                    sequence = HMMSequence(columns=2)
                    sequence.settle(state, title="Start")

                    with self.assertRaises(SequenceError):
                        if action == "cycle":
                            sequence.cycle("D")
                        elif action == "settle":
                            sequence.settle("D")
                        elif action == "finish":
                            sequence.finish()
                        else:
                            sequence.build()

                    sequence.emit("A", title="Label")
                    self.assertEqual(
                        sequence.build(),
                        [
                            Step("Start", committed=(("S", node),)),
                            Step("Label", committed=(("S", node),), emissions=(f"{node}:A",)),
                        ],
                    )

    def test_finish_rejects_initial_insertion_without_a_model_column(self) -> None:
        sequence = HMMSequence()
        sequence.settle("I")
        sequence.emit("A")

        with self.assertRaises(SequenceError):
            sequence.finish()

    def test_bounded_finish_can_fill_every_column_with_deletions(self) -> None:
        sequence = HMMSequence(columns=3)
        sequence.finish(title="Done")

        self.assertEqual(
            sequence.build()[-1].committed,
            (("S", "D1"), ("D1", "D2"), ("D2", "D3"), ("D3", "E")),
        )
        self.assertEqual(sequence.build()[-1].title, "Done")

    def test_finished_sequence_cannot_continue(self) -> None:
        sequence = HMMSequence()
        sequence.settle("M")
        sequence.emit("A")
        sequence.finish()

        with self.assertRaises(SequenceError):
            sequence.settle("M")

    def test_compile_steps_reports_step_title_and_transition(self) -> None:
        with self.assertRaises(FrameCompilationError) as ctx:
            compile_steps([Step("Broken", committed=(("M9", "D11"),))])

        message = str(ctx.exception)
        self.assertIn("step #1", message)
        self.assertIn("'Broken'", message)
        self.assertIn("M9", message)
        self.assertIn("D11", message)

    def test_compile_rejects_structurally_invalid_steps_with_typed_errors(self) -> None:
        invalid_steps = (
            Step(1),  # type: ignore[arg-type]
            Step("Broken", committed=(("S",),)),  # type: ignore[arg-type]
            Step("Broken", scan=("S", 1)),  # type: ignore[arg-type]
            Step("Broken", emissions=(1,)),  # type: ignore[arg-type]
            Step("Broken", flash=(1,)),  # type: ignore[arg-type]
        )
        for step in invalid_steps:
            with self.subTest(step=step):
                with self.assertRaises(FrameCompilationError):
                    compile_step(step)

        with self.assertRaises(FrameCompilationError):
            compile_steps([object()])  # type: ignore[list-item]
        with self.assertRaises(FrameCompilationError):
            compile_steps(None)  # type: ignore[arg-type]

    def test_compile_rejects_invalid_explicit_columns(self) -> None:
        for columns in (0, 1.5, True):
            with self.subTest(columns=columns):
                with self.assertRaises(FrameCompilationError):
                    compile_steps([], columns=columns)  # type: ignore[arg-type]
                with self.assertRaises(FrameCompilationError):
                    compile_step(Step("Broken"), columns=columns)  # type: ignore[arg-type]

    def test_compile_rejects_disconnected_committed_and_scan_paths(self) -> None:
        with self.assertRaises(FrameCompilationError):
            compile_step(
                Step("Disconnected", committed=(("S", "M1"), ("D1", "M2"))),
                columns=2,
            )
        with self.assertRaises(FrameCompilationError):
            compile_step(
                Step("Disconnected scan", committed=(("S", "M1"),), scan=("D1", "M2")),
                columns=2,
            )

    def test_compile_rejects_emissions_that_cannot_be_rendered(self) -> None:
        invalid_emissions = (
            ("M9:A",),
            ("M1:AB",),
            ("M1:A", "M1:B"),
        )
        for emissions in invalid_emissions:
            with self.subTest(emissions=emissions):
                with self.assertRaises(FrameCompilationError):
                    compile_step(Step("Invalid emissions", emissions=emissions), columns=2)
