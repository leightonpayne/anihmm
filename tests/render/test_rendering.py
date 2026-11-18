from __future__ import annotations

import unittest
from io import StringIO

from rich.console import Console
from rich.text import Text
from rich.theme import Theme

from anihmm import (
    AnimationConfigError,
    FrameCompilationError,
    HMMFrame,
    HMMSequence,
    compile_steps,
    print_frame_in_place,
)
from anihmm.render import cells_from_mask, lattice_guide, render_frame


class RenderContractTests(unittest.TestCase):
    def test_render_reserves_emission_rows(self) -> None:
        for emissions, connector, label in (
            ([], "", ""),
            (["", "...."], "", ""),
            (["M1:A"], ":", "A"),
        ):
            with self.subTest(emissions=emissions):
                rows = render_frame(HMMFrame(columns=2, emissions=emissions)).renderables
                self.assertEqual(len(rows), 9)
                self.assertEqual(rows[-2].plain.strip(), connector)
                self.assertEqual(rows[-1].plain.strip(), label)

    def test_render_uses_frame_columns_for_unbounded_sequences(self) -> None:
        sequence = HMMSequence()
        for _ in range(7):
            sequence.settle("M")
            sequence.emit("A")
        sequence.finish()
        frame = compile_steps(sequence.build())[-1]

        rendered = render_frame(frame)
        self.assertEqual(frame.columns, 7)
        self.assertEqual(rendered.renderables[6].plain.count("(M)"), 7)

    def test_unanchored_emissions_use_their_original_column(self) -> None:
        rendered = render_frame(HMMFrame(emissions=["..A.."]))
        self.assertEqual(rendered.renderables[-1].plain[2], "A")

        state_letter = render_frame(HMMFrame(emissions=["..M.."]))
        self.assertEqual(state_letter.renderables[-1].plain[2], "M")

        insertion_letter = render_frame(HMMFrame(emissions=["..I.."]))
        self.assertEqual(insertion_letter.renderables[-1].plain[2], "I")
        self.assertTrue(all(row.plain[2] != ":" for row in insertion_letter.renderables[:-2]))

    def test_glyph_overlays_do_not_shift_explicit_emission_anchors(self) -> None:
        for anchor, row_index, anchor_col in (("M1", 6, 10), ("I1", 3, 13)):
            with self.subTest(anchor=anchor):
                rendered = render_frame(
                    HMMFrame(
                        columns=2,
                        glyph_overlays={(row_index, anchor_col): ("x", "bold")},
                        emissions=[f"{anchor}:A"],
                    )
                )

                self.assertEqual(rendered.renderables[-1].plain[anchor_col], "A")

    def test_render_validates_frame_boundaries(self) -> None:
        invalid_frames = (
            HMMFrame(active_nodes={"M99"}),
            HMMFrame(active_cells={(9, 0)}),
            HMMFrame(active_cells={(0, 999)}),
            HMMFrame(cell_styles={(9, 0): "bold"}),
            HMMFrame(cell_styles={(0, 999): "bold"}),
            HMMFrame(glyph_overlays={(9, 0): ("x", "bold")}),
            HMMFrame(glyph_overlays={(0, 999): ("x", "bold")}),
        )
        for frame in invalid_frames:
            with self.subTest(frame=frame):
                with self.assertRaises(FrameCompilationError):
                    render_frame(frame)

    def test_render_rejects_multi_cell_overlay_glyphs(self) -> None:
        for glyph in ("XX", "界"):
            with self.subTest(glyph=glyph):
                with self.assertRaises(FrameCompilationError):
                    render_frame(HMMFrame(glyph_overlays={(0, 0): (glyph, "bold")}))

    def test_console_rendering_resolves_named_theme_styles(self) -> None:
        frame = HMMFrame(
            cell_styles={(0, 0): "custom"},
            glyph_overlays={(0, 1): ("x", "custom")},
        )
        output = StringIO()
        console = Console(
            file=output,
            force_terminal=True,
            color_system="standard",
            no_color=False,
            theme=Theme({"custom": "bold red"}),
        )
        print_frame_in_place(frame, console=console)
        printed = Text.from_ansi(output.getvalue())
        self.assertEqual(printed.plain[:2], " x")
        for column in (0, 1):
            style = printed.get_style_at_offset(console, column)
            self.assertTrue(style.bold)
            self.assertIsNotNone(style.color)
            self.assertEqual(style.color.get_truecolor(), (128, 0, 0))

        with self.assertRaises(FrameCompilationError):
            print_frame_in_place(
                HMMFrame(cell_styles={(0, 0): "not-a-style"}),
                console=console,
            )

    def test_render_validates_explicit_emission_shape(self) -> None:
        for emission in ("M1:", ":A", "M1:AB", "M1:界"):
            with self.subTest(emission=emission):
                with self.assertRaises(FrameCompilationError):
                    render_frame(HMMFrame(emissions=[emission]))

    def test_render_rejects_non_emitting_and_duplicate_emission_anchors(self) -> None:
        for anchor in ("S", "D1", "E"):
            with self.subTest(anchor=anchor):
                with self.assertRaises(FrameCompilationError):
                    render_frame(HMMFrame(emissions=[f"{anchor}:A"]))

        with self.assertRaises(FrameCompilationError):
            render_frame(HMMFrame(emissions=["M1:A", "M1:B"]))

        with self.assertRaises(FrameCompilationError):
            render_frame(HMMFrame(columns=3, emissions=["M9:A"]))

        for anchor in ("M01", "I00", "M²", "M١"):
            with self.subTest(noncanonical_anchor=anchor):
                with self.assertRaises(FrameCompilationError):
                    render_frame(HMMFrame(emissions=[f"{anchor}:A"]))

    def test_frame_model_rejects_malformed_structures_and_post_init_mutation(self) -> None:
        invalid_frames = (
            lambda: HMMFrame(active_nodes=["S"]),  # type: ignore[arg-type]
            lambda: HMMFrame(active_cells={("x", 0)}),  # type: ignore[arg-type]
            lambda: HMMFrame(cell_styles={(0, 0): 1}),  # type: ignore[dict-item]
            lambda: HMMFrame(glyph_overlays={(0, 0): ("x", 1)}),  # type: ignore[dict-item]
            lambda: HMMFrame(emissions=[1]),  # type: ignore[list-item]
        )
        for frame_factory in invalid_frames:
            with self.subTest(frame_factory=frame_factory):
                with self.assertRaises(AnimationConfigError):
                    frame_factory()

        mutated = HMMFrame()
        mutated.emissions = [1]  # type: ignore[list-item]
        with self.assertRaises(AnimationConfigError):
            render_frame(mutated)

    def test_active_start_and_end_states_use_the_same_style(self) -> None:
        console = Console(file=StringIO(), force_terminal=True)
        active_row = render_frame(HMMFrame(active_nodes={"S", "E"})).renderables[3]
        start_offset = active_row.plain.index("(S)") + 1
        end_offset = active_row.plain.index("(E)") + 1

        self.assertEqual(
            active_row.get_style_at_offset(console, start_offset),
            active_row.get_style_at_offset(console, end_offset),
        )
        self.assertEqual(
            active_row.get_style_at_offset(console, end_offset),
            console.get_style("bold magenta"),
        )

        inactive_row = render_frame(HMMFrame()).renderables[3]
        inactive_end_offset = inactive_row.plain.index("(E)") + 1
        self.assertEqual(
            inactive_row.get_style_at_offset(console, inactive_end_offset),
            console.get_style("grey35"),
        )

    def test_render_helpers_validate_and_parse_masks(self) -> None:
        self.assertEqual(cells_from_mask(""), set())
        self.assertEqual(cells_from_mask(" x.\n .#"), {(0, 0), (1, 1)})
        guide = lattice_guide(columns=2).splitlines()
        self.assertEqual(guide[0], "    012345678901234567890123456")
        self.assertEqual(guide[1].rstrip(), "00      ---->(D)-->(D)-----")
        self.assertEqual(guide[-1].rstrip(), "06      ---->(M)-->(M)-----")
        with self.assertRaises(AnimationConfigError):
            lattice_guide(columns=0)
        with self.assertRaises(AnimationConfigError):
            cells_from_mask(None)  # type: ignore[arg-type]
        for markers in (None, {"XX"}, {1}):
            with self.subTest(markers=markers):
                with self.assertRaises(AnimationConfigError):
                    cells_from_mask("x", markers=markers)  # type: ignore[arg-type]
        for columns in (0, 1.5, True):
            with self.subTest(columns=columns):
                with self.assertRaises(AnimationConfigError):
                    HMMFrame(columns=columns)  # type: ignore[arg-type]

        rendered = render_frame(HMMFrame(), columns=2)
        self.assertEqual(rendered.renderables[6].plain.count("(M)"), 2)
        for columns in (0, 1.5, True):
            with self.subTest(render_columns=columns):
                with self.assertRaises(AnimationConfigError):
                    render_frame(HMMFrame(), columns=columns)  # type: ignore[arg-type]

    def test_overlays_use_terminal_cells_after_combining_glyphs(self) -> None:
        rows = render_frame(
            HMMFrame(glyph_overlays={(0, 0): ("e\u0301", "bold"), (0, 2): ("X", "bold")})
        ).renderables

        self.assertEqual(rows[0].plain[:4], "e\u0301 X")
