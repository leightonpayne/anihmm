from __future__ import annotations

import re
from io import StringIO

import pytest
from rich.console import Console
from rich.text import Text

from anihmm import animate_frames, print_frame_in_place
from anihmm.presets import build_random_path_frame
from anihmm.render import render_frame


class _TerminalBuffer:
    """Interpret the cursor and erase commands used by Rich in these tests."""

    def __init__(self, width: int, height: int = 30) -> None:
        self.width = width
        self.rows = [[" "] * width for _ in range(height)]
        self.row = 0
        self.column = 0

    def feed(self, output: str) -> None:
        tokens = re.finditer(r"\x1b\[([0-9;?]*)([A-Za-z])|([^\x1b])", output)
        consumed = 0
        for token in tokens:
            assert token.start() == consumed, "Unrecognized terminal escape sequence"
            consumed = token.end()
            parameters, command, character = token.groups()
            if command is not None:
                if command == "m" or (command in {"h", "l"} and parameters == "?25"):
                    continue
                amount = int(parameters or "1")
                if command == "A":
                    self.row = max(0, self.row - amount)
                elif command == "B":
                    self.row += amount
                elif command == "G":
                    self.column = amount - 1
                elif command == "K" and amount == 2:
                    self.rows[self.row] = [" "] * self.width
                else:
                    raise AssertionError(f"Unsupported terminal command: {token.group()!r}")
            elif character == "\n":
                self.row += 1
                self.column = 0
            elif character == "\r":
                self.column = 0
            else:
                # Terminals defer autowrap until another printable character arrives.
                if self.column == self.width:
                    self.row += 1
                    self.column = 0
                self.rows[self.row][self.column] = character
                self.column += 1
        assert consumed == len(output), "Unrecognized terminal escape sequence"

    def line(self, index: int) -> str:
        return "".join(self.rows[index])


@pytest.mark.parametrize("width", [80, 40, 20])
def test_replacement_clears_a_wider_animation_without_moving_surrounding_output(
    monkeypatch: pytest.MonkeyPatch, width: int
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    output = StringIO()
    console = Console(
        file=output,
        force_terminal=True,
        no_color=False,
        color_system="standard",
        width=width,
        height=30,
    )
    old_frame = build_random_path_frame(columns=8, emissions="SEARCHING", seed=7)
    new_frame = build_random_path_frame(columns=5, emissions="COMPLETE", seed=7)
    console.print("before")
    animate_frames([old_frame], console=console, hold_final_seconds=0)

    terminal = _TerminalBuffer(width)
    terminal.feed(output.getvalue())
    assert (terminal.row, terminal.column) == (10, 0)
    terminal.rows[12][:5] = "below"
    replacement_start = output.tell()

    print_frame_in_place(new_frame, console=console)
    replacement = output.getvalue()[replacement_start:]
    terminal.feed(replacement)

    assert terminal.line(0) == "before".ljust(width)
    expected_rows = render_frame(new_frame).renderables
    assert [terminal.line(row) for row in range(1, 10)] == [
        row.plain[:width].ljust(width) for row in expected_rows
    ]
    assert terminal.line(12) == "below".ljust(width)
    assert (terminal.row, terminal.column) == (10, 0)
    printed = Text.from_ansi(replacement)
    emission_style = printed.get_style_at_offset(console, printed.plain.index("C"))
    assert emission_style.bold
    assert emission_style.color is not None
    assert emission_style.color.get_truecolor() == (0, 128, 0)

    following_start = output.tell()
    console.print("after")
    terminal.feed(output.getvalue()[following_start:])
    assert terminal.line(10) == "after".ljust(width)


def test_non_terminal_replacement_prints_plain_frame_without_cursor_commands() -> None:
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=80)
    frame = build_random_path_frame(columns=5, emissions="COMPLETE", seed=7)

    print_frame_in_place(frame, console=console)

    assert output.getvalue() == "".join(row.plain + "\n" for row in render_frame(frame).renderables)
