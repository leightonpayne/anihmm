"""Generate or validate the README and documentation animations.

Run with:

    uv run python -m tools.generate_demo_gif
    uv run python -m tools.generate_demo_gif --check
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from rich.color import ColorTriplet
from rich.console import Console
from rich.terminal_theme import TerminalTheme

from anihmm.models import HMMFrame
from anihmm.playback import engine as playback_engine
from anihmm.presets import build_random_frames
from anihmm.render import render_frame
from examples import (
    changing_paths,
    custom_sequence,
    delete_completion,
    fixed_text,
    processing_demo,
    progress_indicator,
    random_emissions,
    transition_previews,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "assets" / "anihmm-demo.gif"
FIXED_TEXT_OUTPUT = ROOT / "docs" / "assets" / "fixed-text.gif"
CUSTOM_SEQUENCE_OUTPUT = ROOT / "docs" / "assets" / "custom-sequence.gif"
RANDOM_EMISSIONS_OUTPUT = ROOT / "docs" / "assets" / "random-emissions.gif"
TRANSITION_PREVIEWS_OUTPUT = ROOT / "docs" / "assets" / "transition-previews.gif"
DELETE_COMPLETION_OUTPUT = ROOT / "docs" / "assets" / "delete-completion.gif"
CHANGING_PATHS_OUTPUT = ROOT / "docs" / "assets" / "changing-paths.gif"
PROCESSING_RESULTS_OUTPUT = ROOT / "docs" / "assets" / "processing-results.gif"
PROGRESS_INDICATOR_OUTPUT = ROOT / "docs" / "assets" / "progress-indicator.gif"

SEEDS = (2, 7, 19)
OVERVIEW_COLUMNS = 8
RENDER_SCALE = 2
FONT_SIZE = 16 * RENDER_SCALE
LINE_HEIGHT = 22 * RENDER_SCALE
CONTENT_PADDING_X = 14 * RENDER_SCALE
CONTENT_PADDING_Y = 12 * RENDER_SCALE
FRAME_DURATION_MS = 50
FINAL_HOLD_MS = 650

EXAMPLES = ROOT / "examples"
PACKAGE_SOURCES = tuple(sorted((ROOT / "src" / "anihmm").rglob("*.py")))
RENDER_ASSETS = (ROOT / "tools" / "assets" / "RobotoMono.ttf",)
GIF_SOURCES = {
    OUTPUT: (),
    FIXED_TEXT_OUTPUT: (EXAMPLES / "fixed_text.py",),
    CUSTOM_SEQUENCE_OUTPUT: (EXAMPLES / "custom_sequence.py",),
    RANDOM_EMISSIONS_OUTPUT: (EXAMPLES / "random_emissions.py",),
    TRANSITION_PREVIEWS_OUTPUT: (EXAMPLES / "transition_previews.py",),
    DELETE_COMPLETION_OUTPUT: (EXAMPLES / "delete_completion.py",),
    CHANGING_PATHS_OUTPUT: (EXAMPLES / "changing_paths.py",),
    PROCESSING_RESULTS_OUTPUT: (EXAMPLES / "processing_demo.py",),
    PROGRESS_INDICATOR_OUTPUT: (EXAMPLES / "progress_indicator.py",),
}
COMMENT_PREFIX = b"anihmm-source-sha256:"

BACKGROUND = (36, 41, 46)
FOREGROUND = (213, 216, 218)

TERMINAL_THEME = TerminalTheme(
    background=BACKGROUND,
    foreground=FOREGROUND,
    normal=[
        BACKGROUND,
        (247, 118, 109),
        (169, 220, 118),
        (255, 216, 102),
        (120, 188, 255),
        (171, 157, 242),
        (120, 220, 232),
        FOREGROUND,
    ],
    bright=[
        (127, 133, 138),
        (247, 118, 109),
        (169, 220, 118),
        (255, 216, 102),
        (120, 188, 255),
        (171, 157, 242),
        (120, 220, 232),
        (250, 250, 248),
    ],
)


def _font_path() -> Path:
    override = os.environ.get("ANIHMM_DEMO_FONT")
    candidates = [
        Path(override) if override else None,
        *RENDER_ASSETS,
        Path.home() / "Library" / "Fonts" / "RobotoMono-Regular.ttf",
        Path("/opt/homebrew/share/fonts/RobotoMono-Regular.ttf"),
        Path("/usr/local/share/fonts/RobotoMono-Regular.ttf"),
        Path("/usr/share/fonts/truetype/roboto/RobotoMono-Regular.ttf"),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    raise RuntimeError("Roboto Mono was not found. Set ANIHMM_DEMO_FONT to its font file path.")


def _fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    regular_path = _font_path()
    bold_path = regular_path.with_name(regular_path.name.replace("Regular", "Bold"))
    if not bold_path.is_file():
        bold_path = regular_path
    regular = ImageFont.truetype(str(regular_path), FONT_SIZE)
    bold = ImageFont.truetype(str(bold_path), FONT_SIZE)
    try:
        regular.set_variation_by_name("Medium")
        bold.set_variation_by_name("Bold")
    except OSError:
        pass
    return regular, bold


def _rgb(style_color) -> tuple[int, int, int]:
    if style_color is None:
        return FOREGROUND
    color: ColorTriplet = style_color.get_truecolor(TERMINAL_THEME)
    rgb = (color.red, color.green, color.blue)
    color_map = {
        (59, 59, 59): (104, 110, 115),
        (89, 89, 89): (135, 140, 145),
        FOREGROUND: (250, 250, 248),
    }
    return color_map.get(rgb, rgb)


def _render_images(
    frames: list[HMMFrame],
    *,
    top_padding_lines: int = 0,
) -> list[Image.Image]:
    rendered_frames = [render_frame(frame) for frame in frames]
    rows = rendered_frames[0].renderables

    regular_font, bold_font = _fonts()
    cell_width = regular_font.getlength("M")
    font_ascent, _ = regular_font.getmetrics()
    line_height = LINE_HEIGHT
    content_padding_x = CONTENT_PADDING_X
    content_padding_y = CONTENT_PADDING_Y + top_padding_lines * line_height
    text_width = max(len(row.plain) for row in rows) * cell_width
    width = math.ceil(text_width) + 2 * content_padding_x + 1
    height = len(rows) * line_height + 2 * CONTENT_PADDING_Y + top_padding_lines * line_height

    console = Console(color_system="truecolor", force_terminal=True)
    images: list[Image.Image] = []
    for rendered in rendered_frames:
        image = Image.new("RGB", (width, height), BACKGROUND)
        draw = ImageDraw.Draw(image)

        for row_index, row in enumerate(rendered.renderables):
            baseline_y = content_padding_y + row_index * line_height + font_ascent
            for column, character in enumerate(row.plain):
                if character == " ":
                    continue
                style = row.get_style_at_offset(console, column)
                x = content_padding_x + column * cell_width
                color = _rgb(style.color)
                font = bold_font if style.bold else regular_font
                draw.text((x, baseline_y), character, font=font, fill=color, anchor="ls")
        images.append(image)

    return images


def _result_summary_image(complete_image: Image.Image, lines: tuple[str, str, str]) -> Image.Image:
    regular_font, _bold_font = _fonts()
    summary_height = 4 * LINE_HEIGHT
    image = Image.new(
        "RGB",
        (complete_image.width, complete_image.height + summary_height),
        BACKGROUND,
    )
    image.paste(complete_image, (0, 0))
    draw = ImageDraw.Draw(image)
    font_ascent, _ = regular_font.getmetrics()
    y = complete_image.height + LINE_HEIGHT + font_ascent
    for text in lines:
        draw.text(
            (CONTENT_PADDING_X, y),
            text,
            font=regular_font,
            fill=FOREGROUND,
            anchor="ls",
        )
        y += LINE_HEIGHT
    return image


def _source_comment(output: Path) -> bytes:
    digest = hashlib.sha256()
    paths = (
        Path(__file__).resolve(),
        *GIF_SOURCES[output],
        *PACKAGE_SOURCES,
        *RENDER_ASSETS,
    )
    digest.update(output.relative_to(ROOT).as_posix().encode())
    for path in paths:
        digest.update(b"\0")
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return COMMENT_PREFIX + digest.hexdigest().encode()


def _save_gif(output: Path, images: list[Image.Image], durations: list[int]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        output,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
        comment=_source_comment(output),
    )
    print(f"Wrote {output.relative_to(ROOT)} ({len(images)} frames)")


def _duration_ms(seconds: float) -> int:
    return max(10, round(seconds * 100) * 10)


def _record_playback(
    run: Callable[[Console], None],
    *,
    loop_hold_ms: int = FINAL_HOLD_MS,
) -> tuple[list[HMMFrame], list[int]]:
    captured: list[tuple[float, HMMFrame]] = []
    terminal_output = StringIO()
    console = Console(
        file=terminal_output,
        force_terminal=True,
        color_system="truecolor",
        width=120,
        height=30,
    )
    started = monotonic()
    render_for_console = playback_engine._render_for_console

    def observe_frame(
        frame: HMMFrame,
        *,
        columns: int | None,
        console: Console,
    ):
        rendered = render_for_console(frame, columns=columns, console=console)
        captured.append((monotonic() - started, frame))
        return rendered

    with patch.object(playback_engine, "_render_for_console", observe_frame):
        run(console)
    finished = monotonic() - started

    timeline: list[tuple[float, HMMFrame]] = []
    for timestamp, frame in captured:
        if timeline and timeline[-1][1] == frame:
            continue
        timeline.append((timestamp, frame))
    if not timeline:
        raise RuntimeError("The example did not render any frames through the playback engine.")

    for (_previous_time, previous), (_current_time, current) in zip(
        timeline, timeline[1:], strict=False
    ):
        start = HMMFrame(columns=current.columns, active_nodes={"S"})
        if current == start and "E" not in previous.active_nodes:
            raise RuntimeError("A recorded playback loop restarted before settling on E.")
    if "E" not in timeline[-1][1].active_nodes:
        raise RuntimeError("The recorded playback ended before settling on E.")

    durations = [
        _duration_ms(next_timestamp - timestamp)
        for (timestamp, _frame), (next_timestamp, _next_frame) in zip(
            timeline, timeline[1:], strict=False
        )
    ]
    durations.append(_duration_ms(finished - timeline[-1][0]) + loop_hold_ms)
    return [frame for _timestamp, frame in timeline], durations


def _write_recorded_gif(
    output: Path,
    run: Callable[[Console], None],
    *,
    loop_hold_ms: int = FINAL_HOLD_MS,
) -> None:
    frames, durations = _record_playback(run, loop_hold_ms=loop_hold_ms)
    _save_gif(output, _render_images(frames), durations)


def _write_processing_results_gif() -> None:
    hit_counts: list[int] = []

    def run(console: Console) -> None:
        hit_counts.extend(processing_demo.main(console))

    frames, durations = _record_playback(run, loop_hold_ms=2_200)
    search_frames = frames[:-1]
    completed_searches = sum(
        "E" in frame.active_nodes
        and "".join(emission.rsplit(":", 1)[-1] for emission in frame.emissions)
        == processing_demo.SEARCH_EMISSIONS
        for frame in search_frames
    )
    partial_text = "".join(emission.rsplit(":", 1)[-1] for emission in search_frames[-1].emissions)
    if completed_searches != 2 or partial_text == processing_demo.SEARCH_EMISSIONS:
        raise RuntimeError(
            "The processing recording must complete two search paths and cut the third short."
        )
    lines = processing_demo.result_lines(hit_counts)
    images = _render_images(frames, top_padding_lines=1)
    result_image = _result_summary_image(images[-1], lines)
    expanded_images = []
    for image in images[:-1]:
        expanded = Image.new("RGB", result_image.size, BACKGROUND)
        expanded.paste(image, (0, 0))
        expanded_images.append(expanded)
    images = [*expanded_images, result_image]
    _save_gif(PROCESSING_RESULTS_OUTPUT, images, durations)


def _run_overview(console: Console) -> None:
    for seed in SEEDS:
        playback_engine.animate_frames(
            build_random_frames(columns=OVERVIEW_COLUMNS, seed=seed),
            fps=1_000 / FRAME_DURATION_MS,
            repeat=False,
            hold_final_seconds=FINAL_HOLD_MS / 1_000,
            console=console,
            enabled=True,
        )


def _generate_gifs() -> None:
    _write_processing_results_gif()
    _write_recorded_gif(PROGRESS_INDICATOR_OUTPUT, progress_indicator.main)
    _write_recorded_gif(OUTPUT, _run_overview, loop_hold_ms=0)
    _write_recorded_gif(FIXED_TEXT_OUTPUT, fixed_text.main)
    _write_recorded_gif(CUSTOM_SEQUENCE_OUTPUT, custom_sequence.main)
    _write_recorded_gif(RANDOM_EMISSIONS_OUTPUT, random_emissions.main)
    _write_recorded_gif(TRANSITION_PREVIEWS_OUTPUT, transition_previews.main)
    _write_recorded_gif(DELETE_COMPLETION_OUTPUT, delete_completion.main)
    _write_recorded_gif(CHANGING_PATHS_OUTPUT, changing_paths.main)


def _check_gifs() -> int:
    stale = []
    for output in GIF_SOURCES:
        if not output.is_file():
            stale.append(output)
            continue
        with Image.open(output) as image:
            if image.info.get("comment") != _source_comment(output):
                stale.append(output)

    if stale:
        for output in stale:
            print(f"Out of date: {output.relative_to(ROOT)}")
        print("Run: uv run python -m tools.generate_demo_gif")
        return 1

    print(f"All {len(GIF_SOURCES)} documentation GIFs match their sources")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when a committed GIF does not match its example source",
    )
    args = parser.parse_args()
    if args.check:
        return _check_gifs()
    _generate_gifs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
