"""
puzzle.py -- turn a puzzle-loop.com "task string" into a grid of clues.

The task string lists the squares row by row, starting top-left:
    digit 0-3  -> a square with that clue
    letter a-z -> that many squares with no clue in a row (a=1, b=2, ... z=26)
    _          -> separator, means nothing

Example (5x5):  a32a33g03c2a3a213

    . 3 2 . 3
    3 . . . .
    . . . 0 3
    . . . 2 .
    3 . 2 1 3
"""

import math
from dataclasses import dataclass

NO_CLUE = None


@dataclass
class Puzzle:
    width: int            # number of squares across
    height: int           # number of squares down
    clues: list           # clues[row][col] = 0..3, or None for no clue
    task: str = ""        # the original task string (needed for the hash check)

    def clue(self, row, col):
        return self.clues[row][col]


def decode_cells(task):
    """Expand the task string into a flat list: one entry per square."""
    cells = []
    for ch in task.strip():
        if ch.isdigit():
            cells.append(int(ch))
        elif ch == "_":
            continue
        elif "a" <= ch <= "z":
            blanks = ord(ch) - ord("a") + 1
            cells.extend([NO_CLUE] * blanks)
        else:
            raise ValueError(f"Unexpected character {ch!r} in task string")
    return cells


def decode_task(task, width=None, height=None):
    """Task string -> Puzzle. Size is worked out from the number of squares
    when the grid is square; otherwise pass width and height."""
    cells = decode_cells(task)
    count = len(cells)

    if width is None and height is None:
        side = math.isqrt(count)
        if side * side != count:
            raise ValueError(
                f"The task string has {count} squares, which is not a square grid. "
                f"Please give the size with --w and --h (e.g. 25x30 puzzles)."
            )
        width = height = side
    elif width is None:
        width = count // height
    elif height is None:
        height = count // width

    if width * height != count:
        raise ValueError(
            f"Size {width}x{height} needs {width * height} squares, "
            f"but the task string has {count}."
        )

    clues = [cells[r * width:(r + 1) * width] for r in range(height)]
    return Puzzle(width, height, clues, task.strip())


def parse_grid_text(text):
    """Hand-typed puzzle -> Puzzle. One row per line, squares separated by
    spaces, '.' for no clue. Example line:  . 3 2 . 3"""
    rows = [line.split() for line in text.strip().splitlines() if line.strip()]
    width = len(rows[0])
    clues = []
    for line_number, row in enumerate(rows, start=1):
        if len(row) != width:
            raise ValueError(f"Line {line_number} has {len(row)} squares, expected {width}")
        clues.append([NO_CLUE if token == "." else int(token) for token in row])
    return Puzzle(width, len(rows), clues, task="")
