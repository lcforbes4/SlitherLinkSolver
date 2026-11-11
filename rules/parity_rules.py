"""Rules that count lines coming in and out (even / odd)."""

from board import EMPTY, LINE, describe_square
from rules.base import rule
from rules.pattern_rules import CORNERS, outside_edges


@rule(19, "Square Parity",
      "One undecided edge entering a square's corners -> odd lines in: fill it, even: cross it")
def square_parity(board, result):
    """
    Look at the edges ENTERING a square (any square, clue or not): at each of its 4 corner
    dots, the edges that aren't the square's own sides (8 in the middle of
    the board, fewer on the border).

            a   c
        + b +   + d +
              S
        + e +   + g +
            f   h

    Every line that enters there has a loose end around the square -- at
    the corner itself, or further along the square's sides if it turned
    there. Loose ends around the square have to pair up, so the number of
    filled entering edges is always EVEN in the finished loop.

    When exactly ONE entering edge is still undecided, count the filled
    ones:
      * odd  -> fill the undecided edge (to make it even)
      * even -> cross it out

    A line that comes into a corner and turns along the square's side still
    counts -- its loose end has just moved along the side:

            │   x
        + x +───+ x +
            x S
        + x +   + x +
            x   ?           1 line enters -> odd -> ? is filled

    Side check: when an ODD number of lines enter, at least one undecided
    entering edge must still become a line. For each undecided SIDE of the
    square, imagine filling it: at each of its two ends, a dot that already
    has 1 line would become full, so its other undecided edges would be
    crossed. If that would cross EVERY undecided entering edge, the count
    could never become even -- so that side can't be filled: cross it out.

            x   x
        + x +   +───+
              S                 3 lines enter (odd). Filling b would fill up
        +───+ b +───+           both bottom dots and cross both edges going
                                down -- nothing left to fix the count -> b is crossed
    """
    for row, col in board.squares():
        entering = [edge for corner in CORNERS for edge in outside_edges(board, (row, col), corner)]
        undecided = board.with_state(entering, EMPTY)
        lines = board.count(entering, LINE)
        why = f"{describe_square(row, col)}: {lines} line{'s' if lines != 1 else ''} enter its corners"

        # exactly one entering edge left: it decides the count
        if len(undecided) == 1:
            if lines % 2 == 1:
                result.fill(undecided[0], why + " (odd) -- the last one must be a line to make it even")
            else:
                result.cross(undecided[0], why + " (even) -- the last one can't be a line")

        # side check: odd so far, so filling a side mustn't close off every way in
        if lines % 2 == 1 and undecided:
            for side in board.with_state(board.square_edges(row, col), EMPTY):
                would_cross = would_be_crossed_if_filled(board, side)
                if all(edge in would_cross for edge in undecided):
                    result.cross(side, why + " (odd) -- filling this side would cross every "
                                             "remaining way in, so the count could never be even")


@rule(23, "Region Parity",
      "A region with only one undecided edge out -> odd loose ends inside: fill it, even: cross it",
      last_resort=True)
def region_parity(board, result):
    """
    Last resort: auto mode only runs it when the other rules are stuck.

    Look only at the UNDECIDED edges and the dots they join. Sometimes one
    undecided edge is the ONLY link between two groups of those dots --
    every other edge leaving one group is already decided. That group is
    a closed-off region with exactly one undecided way in or out.

    Count the LOOSE ENDS inside the region (dots with exactly 1 line).
    Each one has to be finished: paired with another loose end inside,
    or by leaving through the one undecided edge. So:
      * odd  -> one must leave: fill that edge
      * even -> they pair up inside: cross that edge out

          region
        +───────────────+
        │  ╴    ╴    ╴  │       3 loose ends inside (odd)
        │               ╪════  the only undecided way out -> filled
        +───────────────+

    This includes Square Parity (rule 19) as a small case, and works for
    regions of any shape or size.
    """
    for edge, size, loose_ends in regions_with_one_way_out(board):
        why = (f"a closed-off region of {size} dot{'s' if size != 1 else ''} has {loose_ends} "
               f"loose end{'s' if loose_ends != 1 else ''} inside, and this is its only undecided edge")
        if loose_ends % 2 == 1:
            result.fill(edge, why + " (odd -- one must leave)")
        else:
            result.cross(edge, why + " (even -- they pair up inside)")


def regions_with_one_way_out(board):
    """Find every undecided edge that is the ONLY link between two groups
    of dots (joined by undecided edges). Returns a list of
    (edge, number of dots on one side, loose ends on that side).

    How: a depth-first walk over the dots joined by undecided edges. An
    edge is the only link (a "bridge") when nothing below it in the walk
    can reach back above it. The walk also adds up, for each dot, the dots
    and loose ends below it -- which is exactly one side of the bridge."""
    neighbours = {}
    for edge, state in board.state.items():
        if state == EMPTY:
            a, b = board.edge_ends(edge)
            neighbours.setdefault(a, []).append((b, edge))
            neighbours.setdefault(b, []).append((a, edge))

    def is_loose_end(dot):
        return board.count(board.dot_edges(*dot), LINE) == 1

    order, reach = {}, {}            # when each dot was first visited; how far back it can reach
    size, loose = {}, {}             # dots / loose ends at or below each dot in the walk
    found = []

    for start in neighbours:
        if start in order:
            continue
        order[start] = reach[start] = len(order)
        size[start], loose[start] = 1, int(is_loose_end(start))
        stack = [(start, None, iter(neighbours[start]))]

        while stack:
            dot, came_by, options = stack[-1]
            for next_dot, edge in options:
                if edge == came_by:
                    continue
                if next_dot not in order:                    # go deeper
                    order[next_dot] = reach[next_dot] = len(order)
                    size[next_dot], loose[next_dot] = 1, int(is_loose_end(next_dot))
                    stack.append((next_dot, edge, iter(neighbours[next_dot])))
                    break
                reach[dot] = min(reach[dot], order[next_dot])  # a way back up
            else:                                            # finished this dot
                stack.pop()
                if stack:
                    parent = stack[-1][0]
                    reach[parent] = min(reach[parent], reach[dot])
                    size[parent] += size[dot]
                    loose[parent] += loose[dot]
                    if reach[dot] > order[parent]:           # nothing below gets back up
                        found.append((came_by, size[dot], loose[dot]))
    return found


def would_be_crossed_if_filled(board, edge):
    """The undecided edges that would get crossed out if `edge` were filled:
    at each of its two end dots, a dot that already has 1 line would become
    full, so all its other undecided edges would be crossed."""
    crossed = set()
    for dot in board.edge_ends(edge):
        edges = board.dot_edges(*dot)
        if board.count(edges, LINE) == 1:
            crossed.update(e for e in board.with_state(edges, EMPTY) if e != edge)
    return crossed
