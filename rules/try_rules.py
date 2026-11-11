"""Rules that try an edge both ways on a scratch copy of the board."""

from board import CROSS, EMPTY, LINE, describe_edge
from rules.base import RULES, RuleResult, rule, run_rule
from rules.clue_rules import clue_check_at
from rules.line_rules import continue_lines_at, cross_around_full_dots, no_dead_ends_at
from rules.loop_rules import closes_a_small_loop

RADIUS = 3        # how far (in squares) a try may spread from the edge it starts at
MAX_ROUNDS = 5    # how many times a try re-runs all the rules before giving up


@rule(24, "Local Try",
      "Try an edge filled, then crossed, nearby only: if one way breaks something, it's the other",
      last_resort=True)
def local_try(board, result):
    """
    Last resort: auto mode only runs it when the other rules are stuck.

    For every undecided edge, on a scratch copy of the board:
      1. fill it, then work out what follows -- but only within 3 squares
         of that edge:
           * the simple rules after every change (Full Dot, Continue Line,
             No Dead Ends, Clue Check), as far as they go
           * then ALL your normal rules (not the last-resort ones), run on
             just that 3-square area -- and repeat while they find things
      2. if that breaks something (a clue over or under its number, 3 lines
         at a dot, a dead end, an edge wanted both ways, a rule flagging a
         problem, or a small closed loop), the edge can't be a line: cross
         it out
      3. otherwise try it crossed out the same way; if THAT breaks
         something, the edge must be filled

    Nothing is guessed: only a try that breaks something leads to a change,
    and the real board is never touched while trying.
    """
    for edge, state in board.state.items():
        if state != EMPTY:
            continue
        if try_breaks(board, edge, LINE):
            result.cross(edge, f"filling {describe_edge(edge)} breaks something nearby")
        elif try_breaks(board, edge, CROSS):
            result.fill(edge, f"crossing out {describe_edge(edge)} breaks something nearby")


def try_breaks(board, start, value):
    """Set `start` to `value` on a scratch copy focused on the area around
    it, then keep applying rules there. Returns True as soon as anything is
    contradictory, False if nothing breaks."""
    scratch = board.copy()
    scratch.set_focus(start.row, start.col, RADIUS)
    scratch.set(start, value)
    filled = [start] if value == LINE else []
    changed = [start]

    for _ in range(MAX_ROUNDS):
        # the simple rules after every change, as far as they go
        if spread_simple_rules(scratch, changed, start, filled):
            return True

        # then every normal rule, on the focus area only
        changed = []
        for rule_obj in RULES:
            if rule_obj.last_resort:
                continue
            step = run_rule(rule_obj, scratch)
            if step.problems:
                return True
            for change in step.changes:
                if near(change.edge, start) and scratch.get(change.edge) == EMPTY:
                    scratch.set(change.edge, change.new_state)
                    changed.append(change.edge)
                    if change.new_state == LINE:
                        filled.append(change.edge)

        # a small closed loop is never allowed
        if any(closes_a_small_loop(scratch, edge) for edge in filled):
            return True
        if not changed:
            return False
    return False


def spread_simple_rules(scratch, changed, start, filled):
    """Apply the simple rules around every changed edge, and around every
    edge they change, staying near `start`. Returns True if anything breaks."""
    to_check = list(changed)
    while to_check:
        edge = to_check.pop()
        step = RuleResult(scratch, "local try")
        dots = scratch.edge_ends(edge)
        cross_around_full_dots(scratch, step, dots)
        continue_lines_at(scratch, step, dots, flag_branches=True)
        no_dead_ends_at(scratch, step, dots)
        clue_check_at(scratch, step, squares_beside(scratch, edge))
        if step.problems:
            return True

        for change in step.changes:
            if not near(change.edge, start):
                continue                           # stay local
            scratch.set(change.edge, change.new_state)
            to_check.append(change.edge)
            if change.new_state == LINE:
                filled.append(change.edge)
    return False


def squares_beside(board, edge):
    """The (one or two) squares that have this edge as a side."""
    if edge.kind == "H":
        candidates = [(edge.row - 1, edge.col), (edge.row, edge.col)]
    else:
        candidates = [(edge.row, edge.col - 1), (edge.row, edge.col)]
    return [(r, c) for r, c in candidates if 0 <= r < board.height and 0 <= c < board.width]


def near(edge, start):
    return abs(edge.row - start.row) <= RADIUS and abs(edge.col - start.col) <= RADIUS
