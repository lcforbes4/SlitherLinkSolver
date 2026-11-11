"""Rules about the loop as a whole (following the line from end to end)."""

import verify
from board import EMPTY, LINE, describe_dot, describe_edge
from rules.base import rule
from rules.line_rules import forced_follow_up


def line_pieces(board):
    """Find every unfinished piece of line on the board.

    A piece is a chain of LINE edges with two loose ends (dots that have
    only 1 line). Returns a list of (end_a, end_b, number_of_edges)."""
    pieces = []
    visited_ends = set()

    for dot in board.dots():
        if dot in visited_ends or board.count(board.dot_edges(*dot), LINE) != 1:
            continue

        # walk from this loose end along the line until the other loose end
        previous, current, length = None, dot, 0
        while True:
            next_dots = [
                other
                for edge in board.with_state(board.dot_edges(*current), LINE)
                for other in board.edge_ends(edge)
                if other != current and other != previous
            ]
            if not next_dots:
                break                    # reached the other loose end
            previous, current = current, next_dots[0]
            length += 1

        visited_ends.update((dot, current))
        pieces.append((dot, current, length))
    return pieces


def would_be_the_whole_answer(board, piece_length, closing_edge):
    """Would closing this piece finish the puzzle? True if the piece holds
    every line on the board and, with the closing edge added, every clue is
    exactly satisfied."""
    total_lines = sum(1 for s in board.state.values() if s == LINE)
    if total_lines != piece_length:
        return False
    for row, col in board.squares():
        clue = board.clue(row, col)
        if clue is None:
            continue
        sides = board.square_edges(row, col)
        lines = board.count(sides, LINE) + (1 if closing_edge in sides else 0)
        if lines != clue:
            return False
    return True


@rule(8, "No Self Loop",
      "An edge joining the two ends of one piece of line would close a small loop -> cross it")
def no_self_loop(board, result):
    """
    Follow every unfinished piece of line to its two loose ends. If those
    two ends are neighbouring dots, the edge between them would close the
    piece into a loop. A loop that isn't the whole answer is never allowed,
    so cross that edge out.

        before          after

        +───+           +───+
        │   │           │   │
        +   +           + x +      <- closing edge crossed

    (the two loose ends of the line are next to each other, so joining
    them would make a tiny closed loop around one square)

    The one exception: if that piece already holds every line on the board
    and closing it would satisfy every clue, closing it IS the answer, so
    the edge is left alone.
    """
    for end_a, end_b, length in line_pieces(board):
        closing_edge = board.edge_between(end_a, end_b)
        if closing_edge is None or board.get(closing_edge) != EMPTY:
            continue
        if would_be_the_whole_answer(board, length, closing_edge):
            continue
        result.cross(closing_edge,
                     f"{describe_edge(closing_edge)} would close the piece of line "
                     f"between {describe_dot(*end_a)} and {describe_dot(*end_b)} into a small loop")


# ---------- look-ahead: No Self Loop a few forced steps out ----------

def ends_are_close(end_a, end_b):
    """True if two dots are corners of the same square or of two squares
    sharing a side -- close enough that a short forced path could join them."""
    rows_apart, cols_apart = abs(end_a[0] - end_b[0]), abs(end_a[1] - end_b[1])
    return (rows_apart <= 1 and cols_apart <= 2) or (rows_apart <= 2 and cols_apart <= 1)


def closes_a_small_loop(board, edge):
    """Is `edge` part of a closed loop that ISN'T the whole answer?
    Follows the lines from the edge; it's closed if every dot reached has
    exactly 2 lines. It's the whole answer only if it holds every line on
    the board and every clue is satisfied."""
    seen_dots, loop_edges = set(), {edge}
    to_visit = list(board.edge_ends(edge))
    while to_visit:
        dot = to_visit.pop()
        if dot in seen_dots:
            continue
        seen_dots.add(dot)
        lines = board.with_state(board.dot_edges(*dot), LINE)
        if len(lines) != 2:
            return False                       # a loose end (or a branch): not closed
        for line in lines:
            loop_edges.add(line)
            to_visit.extend(board.edge_ends(line))

    total_lines = sum(1 for s in board.state.values() if s == LINE)
    return total_lines != len(loop_edges) or not verify.clues_satisfied(board)


@rule(20, "No Self Loop (Look-Ahead)",
      "Filling an edge at a loose end would force a small loop a few steps later -> cross it",
      last_resort=True)
def no_self_loop_look_ahead(board, result):
    """
    An extension of No Self Loop (rule 8) that looks a few FORCED steps
    ahead. It's a last resort: auto mode only runs it when a whole pass of
    the other rules changes nothing (press 20 to run it yourself any time).

    For every unfinished piece of line whose two loose ends are close (on
    the same square, or on two squares side by side):
      * try each undecided edge at either loose end, on a scratch copy of
        the board: fill it, then follow up as far as it's forced (Full Dot
        + Continue Line -- the same follow-up used after every rule)
      * if that closes a small loop (one that isn't the whole answer), the
        edge can't be a line: cross it out on the real board

        +───+───+
        │       │           filling ? forces the line on round the
        +   + x +           corner (the other ways are crossed), and
        x   ?   x           it would close up with the other end
        +   +   +           -> ? is crossed out
              ...

    Nothing is ever changed on the real board unless the scratch copy
    proves it. The two-step check rule 8 can't see, this one can.
    """
    tried = set()
    for end_a, end_b, length in line_pieces(board):
        if not ends_are_close(end_a, end_b):
            continue
        for end in (end_a, end_b):
            for edge in board.with_state(board.dot_edges(*end), EMPTY):
                if edge in tried:
                    continue
                tried.add(edge)

                scratch = board.copy()
                scratch.set(edge, LINE)
                forced_follow_up(scratch, [edge], "look-ahead",
                                 apply=lambda change: scratch.set(change.edge, change.new_state))
                if closes_a_small_loop(scratch, edge):
                    result.cross(edge, f"filling {describe_edge(edge)} would force a small loop "
                                       f"joining {describe_dot(*end_a)} and {describe_dot(*end_b)}")
