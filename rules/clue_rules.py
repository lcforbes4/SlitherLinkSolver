"""Rules that look at one numbered square and its 4 sides."""

from board import EMPTY, LINE, describe_square
from rules.base import rule


@rule(1, "Clue Check",
      "Clue satisfied -> cross out the rest; exactly enough open sides -> fill them")
def clue_check(board, result):
    """
    For every square with a number:

    (a) it already has as many lines as its number
        -> cross out its remaining empty sides

            +───+          +───+
            │ 2      ->    │ 2 x
            +   +          + x +

    (b) not satisfied yet, but lines + empty sides == number
        -> fill all its empty sides

            + x +          + x +
              3      ->    │ 3 │
            +   +          +───+

    A 0 is satisfied from the start, so (a) crosses all 4 of its sides.

    Flags a problem if a square has MORE lines than its number, or can no
    longer reach its number (too few open sides left).
    """
    clue_check_at(board, result, board.squares())


def clue_check_at(board, result, squares):
    """The Clue Check logic for a given set of squares. Used by the Clue
    Check rule (every square) and by Local Try (only squares near a change)."""
    for row, col in squares:
        clue = board.clue(row, col)
        if clue is None:
            continue

        sides = board.square_edges(row, col)
        lines = board.count(sides, LINE)
        empty = board.with_state(sides, EMPTY)
        where = describe_square(row, col)

        if lines > clue:
            result.flag(f"{where} (clue {clue}) already has {lines} lines")
        elif lines + len(empty) < clue:
            result.flag(f"{where} (clue {clue}) can reach at most {lines + len(empty)} lines")
        elif lines == clue:
            for edge in empty:
                result.cross(edge, f"{where}: clue {clue} is satisfied")
        elif lines + len(empty) == clue:
            for edge in empty:
                result.fill(edge, f"{where}: clue {clue} needs every open side")
