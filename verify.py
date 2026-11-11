"""
verify.py -- is the board a finished, correct answer?

A board is solved when its LINE edges form exactly one closed loop and every
number has exactly that many lines around it. (Edges still EMPTY count as
"not a line".)

If you have the site's fingerprint (hashedSolution), we can also prove the
answer is exactly the site's: the site computes  md5(task + serial),
where serial is board.serialize().
"""

import hashlib

from board import LINE


def site_hash(board):
    return hashlib.md5((board.puzzle.task + board.serialize()).encode()).hexdigest()


def matches_hash(board, expected_hash):
    return site_hash(board) == expected_hash.strip().lower()


def clues_satisfied(board):
    for row, col in board.squares():
        clue = board.clue(row, col)
        if clue is not None and board.count(board.square_edges(row, col), LINE) != clue:
            return False
    return True


def is_single_loop(board):
    """Every dot has 0 or 2 lines, and all the lines are connected."""
    line_edges = [e for e, s in board.state.items() if s == LINE]
    if not line_edges:
        return False

    for row, col in board.dots():
        if board.count(board.dot_edges(row, col), LINE) not in (0, 2):
            return False

    # walk along the lines from one dot and see if we reach them all
    neighbours = {}
    for edge in line_edges:
        a, b = board.edge_ends(edge)
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)

    start = next(iter(neighbours))
    seen, to_visit = {start}, [start]
    while to_visit:
        for nxt in neighbours[to_visit.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                to_visit.append(nxt)
    return len(seen) == len(neighbours)


def is_solved(board):
    return is_single_loop(board) and clues_satisfied(board)


def status_line(board, expected_hash=None):
    """A one-line summary for the bottom of the screen."""
    if not is_solved(board):
        undecided = sum(1 for s in board.state.values() if s.value == "empty")
        return f"Not solved yet -- {undecided} edges undecided."
    if not expected_hash:
        return "SOLVED: one loop and every clue satisfied. (Add --hash to check against the site.)"
    if matches_hash(board, expected_hash):
        return "SOLVED and matches the site's answer ✓"
    return "Loop looks valid, but it does NOT match the site's fingerprint ✗"
