"""
render.py -- draw the board in the terminal.

    +   +───+       +  dot
      3 │ 2 x       ───, │  LINE (part of the loop)
    + x +───+       x  CROSS (not part of the loop)
                    blank  EMPTY (undecided)

Edges changed by the last rule are highlighted in yellow (the very latest
one in bright yellow while animating).
"""

import os
import random
import sys

from board import CROSS, LINE, Edge

# ANSI colour codes (switched off automatically when output isn't a terminal)
RESET = "\033[0m"
BOLD_CYAN = "\033[1;36m"
DIM_RED = "\033[2;31m"
YELLOW = "\033[33m"
BRIGHT_YELLOW = "\033[1;93m"
CLEAR_SCREEN = "\033[2J\033[H"

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(text, color):
    return f"{color}{text}{RESET}" if USE_COLOR and color else text


def _edge_text(board, edge, line_text, cross_text, empty_text, recent, latest):
    state = board.get(edge)
    if state == LINE:
        text, color = line_text, BOLD_CYAN
    elif state == CROSS:
        text, color = cross_text, DIM_RED
    else:
        text, color = empty_text, None
    if edge == latest:
        color = BRIGHT_YELLOW
    elif edge in recent:
        color = YELLOW
    return paint(text, color)


def draw(board, recent=(), latest=None, labels=True):
    """Return the board as a multi-line string.
    recent: edges changed by the last rule (highlighted)
    latest: the single edge just changed (extra bright)
    labels: True  -> show c1 c2 ... above and r1 r2 ... on the left
            False -> no labels, just the board"""
    recent = set(recent)
    lines = []

    if labels:
        # column labels above the squares: c1 c2 c3 ...
        header = "     " + "".join(f"{'c' + str(c + 1):^4}" for c in range(board.width))
        lines.append(header.rstrip())

    for r in range(board.height + 1):
        # dot row: + ─── + ─── +
        row_text = "    +"
        for c in range(board.width):
            row_text += _edge_text(board, Edge("H", r, c), "───", " x ", "   ", recent, latest)
            row_text += "+"
        lines.append(row_text)

        if r == board.height:
            break

        # square row: │ 3 │   x   (row label r1 r2 ... in front)
        row_text = f"{'r' + str(r + 1):>3} " if labels else "    "
        for c in range(board.width + 1):
            row_text += _edge_text(board, Edge("V", r, c), "│", "x", " ", recent, latest)
            if c < board.width:
                clue = board.clue(r, c)
                row_text += f" {clue} " if clue is not None else "   "
        lines.append(row_text)

    return "\n".join(lines)


def show(board, recent=(), latest=None, status_lines=(), clear=True, labels=True):
    """Print the board (optionally clearing the screen first) plus status lines."""
    out = []
    if clear and USE_COLOR:
        out.append(CLEAR_SCREEN)
    out.append(draw(board, recent, latest, labels))
    out.append("")
    out.append("legend:  " + paint("───", BOLD_CYAN) + " line   "
               + paint("x", DIM_RED) + " crossed out   blank = undecided   "
               + paint("yellow", YELLOW) + " = just changed")
    out.extend(status_lines)
    print("\n".join(out), flush=True)


# ---------- the "you solved it" celebration ----------

SPARKLES = "✦·✧"
BANNER = "PUZZLE SOLVED!"
CELEBRATION_WIDTH = 36


def sparkle_line(frame, row):
    """One line of sparkles. Each frame shifts them, so they twinkle."""
    return "".join(SPARKLES[(i + frame + row) % len(SPARKLES)] if (i + frame * 2 + row * 3) % 5 == 0 else " "
                   for i in range(CELEBRATION_WIDTH))


def celebration_lines(frame=0):
    """The three-line celebration: sparkles, banner, sparkles."""
    return ["  " + paint(sparkle_line(frame, 0), BRIGHT_YELLOW),
            "  " + BANNER.center(CELEBRATION_WIDTH - 2),
            "  " + paint(sparkle_line(frame, 1), BRIGHT_YELLOW)]


# The full-screen celebration (plain characters only, no emojis):
#
#   1. fireworks, 5 s         2. the glitter falls...      3. ...and stacks into a box
#
#     .   *       +              *   .  +   o  *             +--------------------+
#   *  . | .  *     PUZZLE         +    .   *                |                    |
#   - - (*) - -     SOLVED!          .  *     +              |   PUZZLE SOLVED!   |
#   *  . | .  *                                              |      30 x 30       |
#     .   *       +              +--------------------+      +--------------------+
#
# The box is built from the bottom up: bottom edge first, then the two
# sides climb, then the top edge drops on.

BOLD = "\033[1m"
BRIGHT_MAGENTA = "\033[1;95m"
BRIGHT_GREEN = "\033[1;92m"
BURST_COLORS = [BRIGHT_YELLOW, BOLD_CYAN, BRIGHT_MAGENTA, BRIGHT_GREEN]
GLITTER = "*+.o"

SCREEN_W, SCREEN_H = 44, 15
BOX_LEFT, BOX_RIGHT, BOX_TOP, BOX_BOTTOM = 3, 40, 4, 12

# fireworks: (row, column, frame it goes off). One round of 8 bursts takes
# 11 frames; the round repeats 4 times, mirrored left-right every other
# round so it doesn't look like the same show twice.
ROUND = [(4, 8, 0), (3, 34, 2), (10, 20, 4), (9, 7, 6), (11, 36, 7),
         (4, 22, 9), (8, 32, 10), (11, 10, 11)]
BURSTS = [(row, col if k % 2 == 0 else SCREEN_W - 1 - col, start + 11 * k)
          for k in range(4) for row, col, start in ROUND]
# the 8 directions a burst throws sparks (columns doubled, since a terminal
# character is about twice as tall as it is wide)
DIRECTIONS = [(-1, 0), (1, 0), (0, -2), (0, 2), (-1, -2), (-1, 2), (1, -2), (1, 2)]
FIREWORK_FRAMES = 50          # x 0.1 s = 5 s
FALL_DELAY = 0.06             # seconds per frame while the glitter falls
HOLD = 1.5                    # seconds the finished box stays up


def _put_text(cells, row, text, color):
    """Write text centred on a screen row."""
    col = (SCREEN_W - len(text)) // 2
    for i, ch in enumerate(text):
        cells[(row, col + i)] = (ch, color)


def _screen(cells):
    """Turn {(row, col): (char, colour)} into lines of text."""
    lines = []
    for r in range(SCREEN_H):
        line = ""
        for c in range(SCREEN_W):
            ch, color = cells.get((r, c), (" ", None))
            line += paint(ch, color) if ch != " " else " "
        lines.append("  " + line.rstrip())
    return lines


def _fireworks(frame):
    """One frame of fireworks. Each burst: a spark, then rings of
    * -> + -> . -> . spreading out, then gone."""
    cells = {}
    for i, (row, col, start) in enumerate(BURSTS):
        age = frame - start
        if not 0 <= age <= 4:
            continue
        color = BURST_COLORS[i % len(BURST_COLORS)]
        if age == 0:
            cells[(row, col)] = ("*", color)
            continue
        char = "*+.."[age - 1]
        radius = min(age, 3)
        for dr, dc in DIRECTIONS:
            r, c = row + dr * radius, col + dc * radius
            if 0 <= r < SCREEN_H and 0 <= c < SCREEN_W:
                cells[(r, c)] = (char, color)
    _put_text(cells, SCREEN_H // 2, BANNER, BOLD)
    return cells


def _box_pieces(rng):
    """Every square of the box's border: (row, col, border char, the frame
    its glitter starts falling, the row it starts from).
    Bottom edge falls first, then the sides one row at a time from the
    bottom up, then the top edge last."""
    pieces = []
    for col in range(BOX_LEFT, BOX_RIGHT + 1):
        char = "+" if col in (BOX_LEFT, BOX_RIGHT) else "-"
        pieces.append((BOX_BOTTOM, col, char, rng.randint(0, 4), rng.randint(0, 3)))
    for step, row in enumerate(range(BOX_BOTTOM - 1, BOX_TOP, -1)):
        for col in (BOX_LEFT, BOX_RIGHT):
            pieces.append((row, col, "|", 5 + step, rng.randint(0, 3)))
    last_side = 5 + (BOX_BOTTOM - BOX_TOP - 2)
    for col in range(BOX_LEFT, BOX_RIGHT + 1):
        char = "+" if col in (BOX_LEFT, BOX_RIGHT) else "-"
        pieces.append((BOX_TOP, col, char, last_side + 1 + rng.randint(0, 3), rng.randint(0, 2)))
    return pieces


def _box_text(cells, details):
    _put_text(cells, BOX_TOP + 2, BANNER, BOLD)
    for i, line in enumerate(list(details)[:3]):
        _put_text(cells, BOX_TOP + 4 + i, line, None)


def celebration_frames(details=(), seed=1):
    """Every frame of the celebration as (lines, seconds to show it).
    details: up to 3 short lines shown in the box under PUZZLE SOLVED!"""
    rng = random.Random(seed)
    frames = [(_screen(_fireworks(f)), 0.1) for f in range(FIREWORK_FRAMES)]

    # the glitter waits at the top, twinkling, then falls 2 rows a frame
    # until it lands on its spot in the box and becomes part of the border
    pieces = _box_pieces(rng)
    frame = 0
    while True:
        cells, landed = {}, 0
        for row, col, char, release, start_row in pieces:
            r = start_row if frame < release else min(row, start_row + 2 * (frame - release))
            if r == row:
                landed += 1
            else:
                cells[(r, col)] = (rng.choice(GLITTER), rng.choice(BURST_COLORS))
        for row, col, char, release, start_row in pieces:     # landed pieces on top
            r = start_row if frame < release else min(row, start_row + 2 * (frame - release))
            if r == row:
                cells[(row, col)] = (char, BRIGHT_YELLOW)
        frames.append((_screen(cells), FALL_DELAY))
        if landed == len(pieces):
            break
        frame += 1

    # the finished box, with the words inside
    _box_text(cells, details)
    frames.append((_screen(cells), HOLD))
    return frames


def celebrate(board=None, labels=True, details=()):
    """Play the full-screen celebration: fireworks, then the glitter falls
    and stacks into a box saying PUZZLE SOLVED! (about 7.5 seconds). The
    caller redraws the board afterwards. In a non-terminal (piped output)
    it just prints the finished box once."""
    import time
    frames = celebration_frames(details)
    if not USE_COLOR:
        print("\n".join(frames[-1][0]), flush=True)
        return
    for lines, delay in frames:
        print(CLEAR_SCREEN + "\n".join(lines), flush=True)
        time.sleep(delay)
