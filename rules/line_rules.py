"""Rules that look at one dot and the edges touching it."""

from board import EMPTY, LINE, describe_dot
from rules.base import RuleResult, rule


def forced_follow_up(board, edges, label, apply):
    """After the given edges change, settle the dots they touch and keep
    going as far as it's forced:

      * a dot with 2 lines        -> cross out its other edges  (Full Dot)
      * a dot with 1 line and only
        one way out               -> fill that way out          (Continue Line)

    `apply(change)` is called for each change (it must put it on the
    board); then the dots that change touches are checked next.
    Used by main.py after every edge a rule draws (apply = draw + animate),
    and by the look-ahead rule on a scratch copy of the board.
    Returns (changes made, problems found)."""
    changes, problems = [], []
    to_check = [dot for edge in edges for dot in board.edge_ends(edge)]
    while to_check:
        dot = to_check.pop(0)
        step = RuleResult(board, label)
        cross_around_full_dots(board, step, [dot])
        continue_lines_at(board, step, [dot])
        for change in step.changes:
            apply(change)
            to_check.extend(board.edge_ends(change.edge))
        changes.extend(step.changes)
        problems.extend(step.problems)
    return changes, problems


@rule(2, "Continue Line",
      "A line reaches a dot with only one open way out -> fill it")
def continue_line(board, result):
    """
    For every dot with exactly 1 line touching it and exactly 1 empty edge
    left (the others are crossed out, or off the edge of the grid):
    the line has to keep going, so fill that empty edge.

                x                    x
            ───+          ->     ───+
                                     │

    Flags a problem if a line reaches a dot with no way out (a dead end),
    or if 3 or more lines meet at one dot (a branch).
    """
    continue_lines_at(board, result, board.dots(), flag_branches=True)


def continue_lines_at(board, result, dots, flag_branches=False):
    """The Continue Line logic for a given set of dots: a dot with 1 line and
    exactly 1 empty edge gets that edge filled; 1 line and no empty edges is
    flagged as a dead end.

    Used by the Continue Line rule (every dot) and by main.py's follow-up
    after every filled edge (only the dots that just changed)."""
    for row, col in dots:
        edges = board.dot_edges(row, col)
        lines = board.count(edges, LINE)
        empty = board.with_state(edges, EMPTY)
        where = describe_dot(row, col)

        if lines >= 3 and flag_branches:
            result.flag(f"{where} has {lines} lines meeting (a branch)")
        elif lines == 1 and len(empty) == 0:
            result.flag(f"{where}: a line ends here with no way out (dead end)")
        elif lines == 1 and len(empty) == 1:
            result.fill(empty[0], f"{where}: only one way for the line to continue")


@rule(7, "Full Dot",
      "A dot already has 2 lines (corner or straight) -> cross out its other edges")
def full_dot(board, result):
    """
    For every dot that already has 2 lines touching it -- whether the line
    turns a corner there or goes straight through -- the loop is finished
    at that dot, so cross out every other edge touching it.

    Corner:                     Straight:

            x                           x
        ───+  x         ->          ───+───
           │                            x

    Flags a problem if 3 or more lines meet at one dot (a branch).
    """
    cross_around_full_dots(board, result, board.dots())


def cross_around_full_dots(board, result, dots):
    """The Full Dot logic for a given set of dots: any dot with 2 lines gets
    its other edges crossed out; 3 or more lines is flagged as a branch.

    Used by the Full Dot rule (every dot) and by main.py's follow-up check
    after every rule (only the dots at the ends of newly filled edges)."""
    for row, col in dots:
        edges = board.dot_edges(row, col)
        lines = board.count(edges, LINE)
        where = describe_dot(row, col)

        if lines >= 3:
            result.flag(f"{where} has {lines} lines meeting (a branch)")
        elif lines == 2:
            for edge in board.with_state(edges, EMPTY):
                result.cross(edge, f"{where} already has 2 lines")


@rule(9, "No Dead Ends",
      "A dot with every edge but one crossed out (or off the grid) -> cross out the last one too")
def no_dead_ends(board, result):
    """
    For every dot with no lines, where all its edges except one are crossed
    out (edges off the grid don't exist, so a border dot has fewer): a line
    coming in along that last edge would have nowhere to go, so cross it out.

    Middle of the grid:          On the top border (no edge above):

            x
        + x + x +                + x + x +
            ?                        ?

    In both, the edge marked ? gets crossed out.

    Flags a problem if a line already ends at a dot with every other edge
    crossed (that line is a dead end).
    """
    no_dead_ends_at(board, result, board.dots())


def no_dead_ends_at(board, result, dots):
    """The No Dead Ends logic for a given set of dots. Used by the No Dead
    Ends rule (every dot) and by Local Try (only dots near a change)."""
    for row, col in dots:
        edges = board.dot_edges(row, col)
        lines = board.with_state(edges, LINE)
        empty = board.with_state(edges, EMPTY)
        where = describe_dot(row, col)

        if len(lines) == 1 and not empty:
            result.flag(f"{where}: a line ends here with no way out (dead end)")
        elif not lines and len(empty) == 1:
            result.cross(empty[0], f"{where}: every other edge is crossed out, a line here would be a dead end")
