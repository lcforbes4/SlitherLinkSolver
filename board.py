"""
board.py -- the state of every edge on the board.

Every edge is in one of three states:
    EMPTY  not decided yet
    CROSS  definitely NOT part of the loop  (drawn as x)
    LINE   definitely part of the loop      (drawn as ─── or │)

How edges are named
-------------------
Dots are counted from the top-left corner, starting at 0:
dot (r, c) is r dots down and c dots across.

    Edge("H", r, c)  horizontal edge from dot (r, c) to dot (r, c+1)
                     r = 0..height, c = 0..width-1
    Edge("V", r, c)  vertical edge from dot (r, c) to dot (r+1, c)
                     r = 0..height-1, c = 0..width

Square (r, c) has dot (r, c) as its top-left corner, so its sides are:

        H(r, c)
    +-----------+
    |           |
 V(r,c)  sq    V(r,c+1)
    |           |
    +-----------+
       H(r+1, c)

In messages for people, squares are shown 1-based ("square row 1, col 1" is
the top-left one) to match the numbers printed around the board.
"""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class EdgeState(Enum):
    EMPTY = "empty"
    CROSS = "cross"
    LINE = "line"


EMPTY, CROSS, LINE = EdgeState.EMPTY, EdgeState.CROSS, EdgeState.LINE


class Edge(NamedTuple):
    kind: str   # "H" or "V"
    row: int
    col: int


@dataclass
class Change:
    """One edge that a rule wants to set, and why."""
    edge: Edge
    new_state: EdgeState
    rule: str
    reason: str


@dataclass
class Problem:
    """Something a rule found that should be impossible (a contradiction)."""
    rule: str
    message: str


def describe_square(row, col):
    return f"square (row {row + 1}, col {col + 1})"


def describe_dot(row, col):
    return f"dot ({row}, {col})"


def describe_edge(edge):
    if edge.kind == "H":
        return f"horizontal edge between dot ({edge.row}, {edge.col}) and ({edge.row}, {edge.col + 1})"
    return f"vertical edge between dot ({edge.row}, {edge.col}) and ({edge.row + 1}, {edge.col})"


class Board:
    def __init__(self, puzzle):
        self.puzzle = puzzle
        self.width = puzzle.width
        self.height = puzzle.height
        self.state = {edge: EMPTY for edge in self.all_edges()}
        self.history = []   # list of steps; each step = list of (edge, old_state)
        self.focus = None   # (top, left, bottom, right) rows/cols: if set, squares()
                            # and dots() only visit that area (used by Local Try)

    def copy(self):
        """A scratch copy of the board to try things on (no undo history).
        Changing the copy never changes the original."""
        scratch = Board(self.puzzle)
        scratch.state = dict(self.state)
        return scratch

    def set_focus(self, row, col, radius):
        """Make squares() and dots() only visit the area within `radius`
        squares of (row, col). Rules then only look at that area -- which
        lets Local Try run every rule cheaply on a small patch."""
        self.focus = (row - radius, col - radius, row + radius, col + radius)

    def _rows_cols(self, max_row, max_col):
        """The row and column ranges to visit (the whole grid, or the focus)."""
        if self.focus is None:
            return range(max_row + 1), range(max_col + 1)
        top, left, bottom, right = self.focus
        return (range(max(0, top), min(max_row, bottom) + 1),
                range(max(0, left), min(max_col, right) + 1))

    # ---------- walking the grid ----------

    def all_edges(self):
        """Every edge in the same order the site uses: all horizontal edges
        row by row, then all vertical edges row by row."""
        for r in range(self.height + 1):
            for c in range(self.width):
                yield Edge("H", r, c)
        for r in range(self.height):
            for c in range(self.width + 1):
                yield Edge("V", r, c)

    def squares(self):
        rows, cols = self._rows_cols(self.height - 1, self.width - 1)
        for r in rows:
            for c in cols:
                yield r, c

    def dots(self):
        rows, cols = self._rows_cols(self.height, self.width)
        for r in rows:
            for c in cols:
                yield r, c

    def clue(self, row, col):
        return self.puzzle.clue(row, col)

    def square_edges(self, row, col):
        """The 4 sides of a square: top, bottom, left, right."""
        return [
            Edge("H", row, col),
            Edge("H", row + 1, col),
            Edge("V", row, col),
            Edge("V", row, col + 1),
        ]

    def dot_edges(self, row, col):
        """The 2 to 4 edges that touch a dot (fewer at the border)."""
        edges = []
        if row > 0:
            edges.append(Edge("V", row - 1, col))   # up
        if row < self.height:
            edges.append(Edge("V", row, col))       # down
        if col > 0:
            edges.append(Edge("H", row, col - 1))   # left
        if col < self.width:
            edges.append(Edge("H", row, col))       # right
        return edges

    def on_board(self, edge):
        return edge in self.state

    @staticmethod
    def edge_ends(edge):
        """The two dots an edge connects."""
        if edge.kind == "H":
            return (edge.row, edge.col), (edge.row, edge.col + 1)
        return (edge.row, edge.col), (edge.row + 1, edge.col)

    def edge_between(self, dot_a, dot_b):
        """The edge joining two neighbouring dots, or None if they aren't neighbours."""
        (r1, c1), (r2, c2) = dot_a, dot_b
        if r1 == r2 and abs(c1 - c2) == 1:
            edge = Edge("H", r1, min(c1, c2))
        elif c1 == c2 and abs(r1 - r2) == 1:
            edge = Edge("V", min(r1, r2), c1)
        else:
            return None
        return edge if self.on_board(edge) else None

    # ---------- reading ----------

    def get(self, edge):
        return self.state[edge]

    def count(self, edges, wanted_state):
        return sum(1 for e in edges if self.state[e] == wanted_state)

    def with_state(self, edges, wanted_state):
        return [e for e in edges if self.state[e] == wanted_state]

    def is_full(self):
        return all(s != EMPTY for s in self.state.values())

    # ---------- changing ----------

    def set(self, edge, new_state):
        """Set one edge and return its old state."""
        old = self.state[edge]
        self.state[edge] = new_state
        return old

    def start_step(self):
        self.history.append([])

    def apply_change(self, change):
        """Apply one change as part of the current step (so undo can reverse it)."""
        old = self.set(change.edge, change.new_state)
        self.history[-1].append((change.edge, old))

    def apply(self, changes):
        """Apply a whole list of changes as one undoable step."""
        self.start_step()
        for change in changes:
            self.apply_change(change)

    def undo(self):
        """Reverse the last step. Returns False if there is nothing to undo."""
        while self.history and not self.history[-1]:
            self.history.pop()          # skip steps that changed nothing
        if not self.history:
            return False
        for edge, old in reversed(self.history.pop()):
            self.state[edge] = old
        return True

    # ---------- for the hash check ----------

    def serialize(self):
        """The site's answer format: 'y' for every LINE edge, 'n' otherwise."""
        return "".join("y" if self.state[e] == LINE else "n" for e in self.all_edges())
