"""Rules that recognise a fixed pattern of clues."""

from board import CROSS, EMPTY, LINE, Edge, describe_dot, describe_square
from rules.base import rule


# ---------- shared helpers for corner / diagonal rules ----------

# The 4 corners of a square: where its dot is (row/col offset from the
# square), which 2 sides meet there, which way is diagonally AWAY from it
# (across the square, to the opposite corner), and the opposite corner.
CORNERS = {
    "top-left":     {"dot": (0, 0), "sides": ("top", "left"),     "away": (+1, +1), "opposite": "bottom-right"},
    "top-right":    {"dot": (0, 1), "sides": ("top", "right"),    "away": (+1, -1), "opposite": "bottom-left"},
    "bottom-left":  {"dot": (1, 0), "sides": ("bottom", "left"),  "away": (-1, +1), "opposite": "top-right"},
    "bottom-right": {"dot": (1, 1), "sides": ("bottom", "right"), "away": (-1, -1), "opposite": "top-left"},
}


def corner_sides(board, row, col, corner):
    """The two sides of square (row, col) that meet at the given corner."""
    top, bottom, left, right = board.square_edges(row, col)
    named = {"top": top, "bottom": bottom, "left": left, "right": right}
    return [named[name] for name in CORNERS[corner]["sides"]]


def corner_dot(row, col, corner):
    """The dot at the given corner of square (row, col)."""
    offset_r, offset_c = CORNERS[corner]["dot"]
    return row + offset_r, col + offset_c


def clue_at(board, row, col):
    """The clue at (row, col), or None if blank or off the grid."""
    if 0 <= row < board.height and 0 <= col < board.width:
        return board.clue(row, col)
    return None


def square_and_2s_beyond(board, row, col, corner):
    """The square itself, then every 2 in an unbroken diagonal chain going
    out from it through `corner`.  E.g. for the top-left corner of the
    square at (4, 4): [(4, 4), (3, 3), (2, 2)] if (3, 3) and (2, 2) are 2s."""
    step_r, step_c = -CORNERS[corner]["away"][0], -CORNERS[corner]["away"][1]
    squares = [(row, col)]
    while clue_at(board, squares[-1][0] + step_r, squares[-1][1] + step_c) == 2:
        squares.append((squares[-1][0] + step_r, squares[-1][1] + step_c))
    return squares


def outside_edges(board, square, corner):
    """The edges at a square's corner dot that are NOT the square's own sides."""
    sides = board.square_edges(*square)
    return [e for e in board.dot_edges(*corner_dot(*square, corner)) if e not in sides]


def diagonal_neighbour(row, col, corner):
    """The square diagonally past the given corner of square (row, col).
    It touches (row, col) at that corner dot -- at ITS opposite corner."""
    step_r, step_c = CORNERS[corner]["away"]
    return row - step_r, col - step_c


def diagonal_path(board, square, corner):
    """Walk from `square` diagonally AWAY from its `corner`, through any
    unbroken chain of 2s. Returns (twos, end): the 2s walked through (the
    starting square counts if it's a 2), and the first square that isn't
    a 2 -- or None if the walk runs off the grid."""
    step_r, step_c = CORNERS[corner]["away"]
    twos = []
    r, c = square
    while clue_at(board, r, c) == 2:
        twos.append((r, c))
        r, c = r + step_r, c + step_c
    on_grid = 0 <= r < board.height and 0 <= c < board.width
    return twos, ((r, c) if on_grid else None)


def entering_lines(board, square, corner):
    """(lines, others): the outside edges at a square's corner that are
    LINEs, and the rest of the outside edges there."""
    outside = outside_edges(board, square, corner)
    lines = board.with_state(outside, LINE)
    return lines, [e for e in outside if e not in lines]


# ---------- shared "Line Into" logic ----------
#
# When EXACTLY ONE line reaches a square at one of its corners (from
# outside), that square has exactly one of its own sides at that corner.
# What that means for the square's two FAR sides depends on its clue.

def one_line_reaches(board, result, square, corner, why):
    """Exactly one line reaches `square` at its `corner`. Apply the result
    to the square's two far sides (the sides at the opposite corner):

        1  -> its one line is used up: cross out both far sides
        3  -> its missing side touches this corner: fill both far sides
        2  -> exactly one far side is a line: if one is crossed, fill the
              other (flags a problem if both are crossed)
    """
    clue = clue_at(board, *square)
    far_a, far_b = corner_sides(board, *square, CORNERS[corner]["opposite"])
    where = f"{why}: one line reaches the {clue} at {describe_square(*square)}"

    if clue == 1:
        result.cross(far_a, where)
        result.cross(far_b, where)
    elif clue == 3:
        result.fill(far_a, where)
        result.fill(far_b, where)
    elif clue == 2:
        crossed = [e for e in (far_a, far_b) if board.get(e) == CROSS]
        if len(crossed) == 2:
            result.flag(f"{where}, but both of its far sides are crossed out")
        elif len(crossed) == 1:
            result.fill(far_b if crossed[0] == far_a else far_a, where + " and one far side is crossed")


def one_line_out(board, result, square, corner, why):
    """Exactly one of `square`'s own sides at `corner` is a line, so exactly
    one line has to leave through the OUTSIDE edges at that corner dot:

        two outside edges  -> they're opposites: one filled -> cross the
                              other; one crossed -> fill the other
                              (flags a problem if both filled / both crossed)
        one outside edge   -> (the other is off the grid) fill it
        none (grid corner) -> nothing to do
    """
    outside = outside_edges(board, square, corner)
    where = f"{why}: exactly one line leaves through {describe_dot(*corner_dot(*square, corner))}"

    if len(outside) == 1:
        result.fill(outside[0], where + " (the other way is off the grid)")
    elif len(outside) == 2:
        first, second = outside
        if board.get(first) == board.get(second) != EMPTY:
            result.flag(f"{where}, but both edges there are {board.get(first).value}")
            return
        for edge, other in ((first, second), (second, first)):
            if board.get(edge) == LINE:
                result.cross(other, where + " (the other edge is filled)")
            elif board.get(edge) == CROSS:
                result.fill(other, where + " (the other edge is crossed)")


def one_line_enters(board, result, square, corner, why, clues=(1, 2, 3)):
    """Exactly one line enters `square` at its `corner` (from outside, and
    can't turn away). A chain of 2s passes "exactly one" along the diagonal,
    so walk away from that corner and apply one_line_reaches to every 2 on
    the way and to the square at the end -- only for the given clues."""
    twos, end = diagonal_path(board, square, corner)
    if 2 in clues:
        for two in twos:
            one_line_reaches(board, result, two, corner, why)
    if end is not None and clue_at(board, *end) in clues:
        via = "" if not twos else f" (through a chain of {len(twos)} 2s)"
        one_line_reaches(board, result, end, corner, why + via)


def one_line_out_of_2s(board, result, square, corner, why):
    """Exactly one line enters `square` at its `corner`. Every 2 on the
    diagonal walk from there (see diagonal_path) then has exactly one line
    at its FAR corner too, so the two outside edges there are opposites
    (one_line_out)."""
    far_corner = CORNERS[corner]["opposite"]
    twos, _ = diagonal_path(board, square, corner)
    for two in twos:
        one_line_out(board, result, two, far_corner, f"{why}, through the 2 at {describe_square(*two)}")


@rule(3, "Adjacent Threes",
      "Two 3s sharing a side -> fill shared + far edges, cross the shared edge's extensions")
def adjacent_threes(board, result):
    """
    For every pair of 3s that share a side:
      * fill the shared edge between them
      * fill each 3's far side (opposite the shared edge)
      * cross out the two edges that continue the shared edge's line
        beyond the pair (skipped where that would be off the grid)

    Side by side:                 Stacked:

        +   +   +                     +───+
            x                           3
        +   +   +                 x   +───+   x
        │ 3 │ 3 │                       3
        +   +   +                     +───+
            x
        +   +   +

    Chains like 3 3 3 need nothing special: each neighbouring pair is
    handled on its own and the results agree.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue

        # neighbour to the RIGHT is also a 3  ->  side by side
        if col + 1 < board.width and board.clue(row, col + 1) == 3:
            why = f"{describe_square(row, col)} and the 3 to its right"
            result.fill(Edge("V", row, col), why)          # far left
            result.fill(Edge("V", row, col + 1), why)      # shared
            result.fill(Edge("V", row, col + 2), why)      # far right
            for extension in (Edge("V", row - 1, col + 1), Edge("V", row + 1, col + 1)):
                if board.on_board(extension):
                    result.cross(extension, why)

        # neighbour BELOW is also a 3  ->  stacked
        if row + 1 < board.height and board.clue(row + 1, col) == 3:
            why = f"{describe_square(row, col)} and the 3 below it"
            result.fill(Edge("H", row, col), why)          # far top
            result.fill(Edge("H", row + 1, col), why)      # shared
            result.fill(Edge("H", row + 2, col), why)      # far bottom
            for extension in (Edge("H", row + 1, col - 1), Edge("H", row + 1, col + 1)):
                if board.on_board(extension):
                    result.cross(extension, why)


@rule(4, "Three in a Corner",
      "A 3's corner with no way out (crossed or off the grid) -> fill the 3's two sides at that corner")
def three_in_a_corner(board, result):
    """
    For every 3, look at each of its 4 corner dots. The dot has edges that
    are the 3's own sides, and edges pointing AWAY from the 3. If every
    edge pointing away is crossed out (or doesn't exist because it's off
    the grid), the line can't leave through that corner, so both of the
    3's sides that meet there must be filled.

    Grid corner (no outside edges at all):

        +   +            +───+
          3        ->    │ 3
        +   +            +   +

    In the middle, with the outside edges crossed out:

              x                      x
        + x +   +          + x +───+
              3      ->          │ 3
            +   +                +   +

    (top-left corner of the 3: the edge above it and the edge to its
    left are crossed, so the 3's top and left sides get filled)

    Flags a problem (via fill) if one of those two sides is already crossed.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue

        sides = board.square_edges(row, col)
        top, bottom, left, right = sides

        # each corner dot of the square, with the 3's two sides that touch it
        corners = [
            ((row, col), top, left),                  # top-left
            ((row, col + 1), top, right),             # top-right
            ((row + 1, col), bottom, left),           # bottom-left
            ((row + 1, col + 1), bottom, right),      # bottom-right
        ]

        for (dot_row, dot_col), side_a, side_b in corners:
            outside = [e for e in board.dot_edges(dot_row, dot_col) if e not in sides]
            if all(board.get(e) == CROSS for e in outside):   # off-grid edges aren't listed
                why = (f"{describe_square(row, col)}: no way out at its corner "
                       f"{describe_dot(dot_row, dot_col)}")
                result.fill(side_a, why)
                result.fill(side_b, why)


@rule(5, "Diagonal Threes",
      "3s in a diagonal line (touching, or with only 2s between) -> fill the outer corner of each end 3")
def diagonal_threes(board, result):
    """
    For every unbroken diagonal line of 2 or more 3s (each 3 touching the
    next one corner to corner), fill the two sides that make the OUTER
    corner of each end 3 -- the corner pointing away along the diagonal.
    The 3s in the middle of a longer line are left alone.

    Also works for two 3s with a diagonal chain of only 2s between them
    (3, 2, 3  or  3, 2, 2, 2, 3). Mixed chains (3, 2, 3, 2, 3) are not
    treated as one line. The 2s are left alone.

        +───+   +   +
        │ 3
        +   +   +   +
              2
        +   +   +   +
                  3 │
        +   +   +───+

    Going down-right:                 Going down-left:

        +───+   +                         +   +───+
        │ 3                                     3 │
        +   +   +              or         +   +   +
              3 │                         │ 3
        +   +───+                         +───+   +

    A line of three 3s works the same way: only the first and last 3 get
    their outer corner filled.

    Each outer corner dot then has 2 lines, so its other edges (pointing
    away from the 3) are crossed out too, skipping any off the grid:

            x
        x +───+   +
            │ 3
            +   +   +
                  3 │
            +   +───+ x
                      x
    """
    def fill_outer_corner(square, corner, why):
        """Fill the 3's two sides at `corner`, then cross out the other
        edges at that corner dot (it now has 2 lines, so it's full)."""
        side_a, side_b = corner_sides(board, *square, corner)
        result.fill(side_a, why)
        result.fill(side_b, why)
        for edge in board.dot_edges(*corner_dot(*square, corner)):
            if edge not in (side_a, side_b):
                result.cross(edge, why + " (outer corner is full)")

    # (column step, name, outer corner of the START 3, outer corner of the END 3)
    directions = [
        (+1, "down-right", "top-left", "bottom-right"),
        (-1, "down-left", "top-right", "bottom-left"),
    ]

    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue

        for step, name, start_corner, end_corner in directions:
            # --- a line of touching 3s: only start at the first 3 of the line
            if clue_at(board, row - 1, col - step) != 3:
                end_row, end_col = row, col
                while clue_at(board, end_row + 1, end_col + step) == 3:
                    end_row, end_col = end_row + 1, end_col + step

                length = end_row - row + 1
                if length >= 2:
                    why = (f"diagonal line of {length} 3s ({name}) from "
                           f"{describe_square(row, col)} to {describe_square(end_row, end_col)}")
                    fill_outer_corner((row, col), start_corner, why)
                    fill_outer_corner((end_row, end_col), end_corner, why)

            # --- a 3, then only 2s, then a 3
            r, c = row + 1, col + step
            twos = 0
            while clue_at(board, r, c) == 2:
                r, c, twos = r + 1, c + step, twos + 1
            if twos >= 1 and clue_at(board, r, c) == 3:
                why = (f"3s with {twos} 2{'s' if twos > 1 else ''} between them ({name}) from "
                       f"{describe_square(row, col)} to {describe_square(r, c)}")
                fill_outer_corner((row, col), start_corner, why)
                fill_outer_corner((r, c), end_corner, why)


@rule(6, "Line Into a 3",
      "A line enters a 3's corner (directly or through a diagonal chain of 2s) -> no turning away, fill the 3's far sides")
def line_into_a_3(board, result):
    """
    A LINE comes into a corner dot from outside. That corner belongs either
    to:

      * a 3 directly, or
      * a 2 at the end of an unbroken diagonal chain of 2s leading to a 3

    Then:
      * the line must not turn away -- cross out the other outside edge(s)
        at the dot where it enters
      * fill the 3's two FAR sides (away from the corner facing the line)

    Directly:                     Through a chain of 2s:

              │                         │
          + x +   +                 + x +   +   +   +
                3 │                       2
              +───+                     +   +   +   +
                                              2
                                        +   +   +   +
                                                  3 │
                                            +   +───+

    Why: if the line turned away, the first square would have no line at
    that corner. For a 3 that leaves at most 2 lines. Through a chain, each
    2 then has both its lines at its far corner, which forces the next
    square to have none at the shared corner -- all the way to the 3, which
    can't have none at any corner. So the line goes along exactly ONE side
    of the first square; "exactly one" carries down the chain, so the 3's
    missing side touches that corner and both far sides are lines.

    At the border there may be no outside edge to cross; the far sides are
    still filled. Flags a problem if 2 lines meet at the entering corner
    from outside (the line already turned away).
    """
    for square in board.squares():
        for corner in CORNERS:
            lines, others = entering_lines(board, square, corner)
            if not lines:
                continue
            twos, end = diagonal_path(board, square, corner)
            if end is None or clue_at(board, *end) != 3:
                continue                                   # this line isn't heading into a 3

            where = f"line at {describe_dot(*corner_dot(*square, corner))}"
            if len(lines) > 1:
                result.flag(f"{where} turns away, but the 3 at {describe_square(*end)} "
                            f"needs a line at that corner")
                continue

            for edge in others:
                result.cross(edge, f"{where} heads into the 3 at {describe_square(*end)} "
                                   f"and can't turn away")
            one_line_reaches(board, result, end, corner, where)


@rule(10, "Two in a Corner",
      "A 2 with a dead corner: fill corner if a far side is crossed; matching edges; Line Into off its other corners")
def two_in_a_corner(board, result):
    """
    For every 2, look at each of its 4 corner dots. A corner is DEAD when
    every edge at that dot that isn't one of the 2's own sides is crossed
    out (or off the grid) -- the line can't leave the 2 through it.

    (a) Dead corner AND at least one of the 2's two FAR sides (the ones
        not touching that corner) is crossed out:
          * fill the 2's two sides that meet at the dead corner
          * cross out the 2's other two sides (the 2 is now satisfied)

            before                 after
                  x                      x
              + x +   +            + x +───+
                    2 x                  │ 2 x
                  +   +                  + x +

        Why: at a dead corner the 2's two sides there are either both
        lines or both empty. Both empty would need both far sides filled
        -- impossible, one is crossed. So both are lines.

    (b) Dead corner: at the 2's OPPOSITE corner the two outside edges
        (edges leading into the 2 there) MATCH:
          * one crossed out -> cross out the other
          * one filled      -> fill the other

            before            after
            +   +   +         +   +   +
              2                 2
            +   + x +         +   + x +
                                  x
            +   +   +         +   +   +

        Why: the 2 has either both lines at the dead corner (none at the
        opposite one, so the outside edges there are both lines or both
        empty) or both lines at the opposite corner (that dot is full, so
        both outside edges are empty). Either way they match.

        Also works along a diagonal chain of 2s going away from the dead
        corner: each 2 in the chain has 0 or 2 lines at its far corner, so
        the outside edges at the far corner of EVERY 2 in the chain match.

        On the border, one of the two outside edges doesn't exist -- it
        counts as crossed, so the one that does exist is crossed out.

    (c) Dead corner: at each of the 2's two OTHER corners (not the dead one,
        not its opposite) exactly one of the 2's sides is a line -- so
        exactly one line leaves the 2 there. Apply the Line Into results
        to the square diagonally past each of those corners (through any
        chain of 2s): a 1 gets its far sides crossed, a 3 gets its far
        sides filled, a 2 with one far side crossed gets the other filled.

            before                after
            +   +   +   +         +   +   +───+
                x     3               x     3 │
            + x +   +   +         + x +   +   +
                  2                     2
            +   +   +   +         +   +   +   +

        Why: the 2's sides at the dead corner are both lines (top + left)
        or both empty (so bottom + right). Either way the top-right corner
        gets exactly one of them (top, or right), and so does bottom-left.

        Also at each of those corners: the line leaving the 2 has to go out
        through exactly one of the outside edges there, so they're
        opposites. One filled -> cross the other; one crossed (or off the
        grid) -> fill the other.

        And the 2s diagonally past those corners pass "exactly one" on: at
        each such 2's far corner the two outside edges are opposites too.

        All of (c) also applies to every 2 in the diagonal chain going away
        from the dead corner -- each has 0 or 2 lines at its near corner,
        so it too has exactly one line at each of its other two corners.

            +   +   +
            x                   the 2's top-left corner is dead, so
            +   +   +           exactly one line leaves its bottom-left
              2                 corner -- on the border the only way out
            +   +   +           is down
            │
            +   +   +

    Flags a problem (via fill/cross) if an edge is already the opposite.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 2:
            continue

        for corner, info in CORNERS.items():
            outside = outside_edges(board, (row, col), corner)
            if not all(board.get(e) == CROSS for e in outside):
                continue                                   # not a dead corner
            dead_dot = describe_dot(*corner_dot(row, col, corner))
            opposite = info["opposite"]

            # (a) a far side is crossed -> fill the dead corner, cross the rest
            far_sides = corner_sides(board, row, col, opposite)
            if any(board.get(e) == CROSS for e in far_sides):
                why = f"{describe_square(row, col)}: dead corner at {dead_dot} and a far side is crossed out"
                for edge in corner_sides(board, row, col, corner):
                    result.fill(edge, why)
                for edge in far_sides:
                    result.cross(edge, why + " (the 2 is satisfied)")

            # (b) at the far corner of this 2 and of every 2 in the diagonal
            # chain beyond it, the two outside edges MATCH:
            #   one crossed (or off the grid) -> cross the other
            #   one filled                     -> fill the other
            for distance, two in enumerate(square_and_2s_beyond(board, row, col, opposite)):
                far_outside = outside_edges(board, two, opposite)
                via = "" if distance == 0 else f" (through a chain of {distance + 1} 2s)"
                why = (f"{describe_square(row, col)}: dead corner at {dead_dot}{via}, so the outside "
                       f"edges at {describe_dot(*corner_dot(*two, opposite))} match")
                if len(far_outside) == 1:
                    result.cross(far_outside[0], why + " (the other one is off the grid)")
                elif len(far_outside) == 2:
                    for edge, other in ((far_outside[0], far_outside[1]), (far_outside[1], far_outside[0])):
                        if board.get(edge) == CROSS:
                            result.cross(other, why)
                        elif board.get(edge) == LINE:
                            result.fill(other, why)

            # (c) exactly one line leaves at each of the two OTHER corners --
            # of this 2, and of every 2 in the diagonal chain going away from
            # the dead corner (each has 0 or 2 lines at its near corner too)
            for distance, two in enumerate(square_and_2s_beyond(board, row, col, opposite)):
                via = "" if distance == 0 else f", through the chain to the 2 at {describe_square(*two)}"
                for side_corner in CORNERS:
                    if side_corner in (corner, opposite):
                        continue
                    why = (f"{describe_square(row, col)}: dead corner at {dead_dot}{via}, so exactly "
                           f"one line leaves its {side_corner} corner")

                    # the outside edges there are opposites
                    one_line_out(board, result, two, side_corner, why)

                    # the square diagonally past that corner gets exactly one
                    # line: Line Into results, and every 2 on the way passes
                    # "exactly one" on to its far corner
                    neighbour = diagonal_neighbour(*two, side_corner)
                    facing = CORNERS[side_corner]["opposite"]
                    one_line_enters(board, result, neighbour, facing, why)
                    one_line_out_of_2s(board, result, neighbour, facing, why)


@rule(11, "Diagonal Lines Into a 2",
      "Lines enter opposite outer corners of a 2 (or a diagonal chain of 2s) -> they can't turn away")
def diagonal_lines_into_a_2(board, result):
    """
    Take a 2, or an unbroken diagonal chain of 2s (each touching the next
    corner to corner). If a line comes in from outside at BOTH outer ends
    of the chain -- the far corner of the first 2 and the far corner of the
    last 2 -- then neither line may turn away from the 2s. At each of those
    two corners, cross out the other outside edge.

    Single 2:                        Chain of two 2s:

          │                                │
      + x +   +   +                    + x +   +   +
            2                                2
          +   + x +                        +   +   +   +
              │                                    2
                                               +   +   + x +
                                                       │

    Why: if a line turned away at one end, the first 2's sides at that
    corner are both empty, so its 2 lines sit at the opposite corner. That
    corner is shared with the next 2, so the next 2's sides there must be
    empty -- and so on down the chain, until the last 2 has both its lines
    at the far end, where a line already comes in: 3 lines at one dot.

    Every stretch of a longer chain is checked, so a line entering in the
    middle of a chain also counts. Edges off the grid don't exist, so at the
    border there may be nothing to cross.
    """
    def is_two(r, c):
        return 0 <= r < board.height and 0 <= c < board.width and board.clue(r, c) == 2

    def line_from_outside(square, dot):
        """The outside edges at `dot` (edges not belonging to `square`),
        if exactly one of them is a LINE. Otherwise None."""
        sides = board.square_edges(*square)
        outside = [e for e in board.dot_edges(*dot) if e not in sides]
        return outside if board.count(outside, LINE) == 1 else None

    # step = column change per row: +1 is the down-right diagonal, -1 is down-left
    for step in (+1, -1):
        for row, col in board.squares():
            # only start at the first 2 of a chain
            if not is_two(row, col) or is_two(row - 1, col - step):
                continue
            chain = [(row, col)]
            while is_two(chain[-1][0] + 1, chain[-1][1] + step):
                chain.append((chain[-1][0] + 1, chain[-1][1] + step))

            # check every stretch first..last of the chain (a single 2 included)
            for i in range(len(chain)):
                for j in range(i, len(chain)):
                    first, last = chain[i], chain[j]
                    # the outer corner of `first` points up the diagonal,
                    # the outer corner of `last` points down it
                    if step == +1:
                        first_dot = (first[0], first[1])              # top-left
                        last_dot = (last[0] + 1, last[1] + 1)         # bottom-right
                    else:
                        first_dot = (first[0], first[1] + 1)          # top-right
                        last_dot = (last[0] + 1, last[1])             # bottom-left

                    outside_a = line_from_outside(first, first_dot)
                    outside_b = line_from_outside(last, last_dot)
                    if outside_a is None or outside_b is None:
                        continue

                    count = j - i + 1
                    what = "a 2" if count == 1 else f"a diagonal chain of {count} 2s"
                    why = (f"lines enter both ends of {what} "
                           f"({describe_square(*first)} to {describe_square(*last)}) and can't turn away")
                    for edge in board.with_state(outside_a + outside_b, EMPTY):
                        result.cross(edge, why)


@rule(12, "One in a Corner",
      "A 1 with a dead corner (grid corner, or outside edges crossed) -> cross its two sides there")
def one_in_a_corner(board, result):
    """
    For every 1, look at each of its 4 corner dots. A corner is DEAD when
    every edge at that dot that isn't one of the 1's own sides is crossed
    out (or off the grid -- so a 1 in a grid corner always has one).

    At a dead corner the line either uses BOTH of the 1's sides there
    (turning around the corner) or NEITHER. Both would give the 1 two
    lines -- too many -- so cross out both.

    Grid corner:                 In the middle:

        +   +        + x +             x                  x
          1     ->   x 1           + x +   +    ->    + x + x +
        +   +        +   +               1                  x 1
                                       +   +                +   +

    Flags a problem (via cross) if one of those sides is already a line.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 1:
            continue

        sides = board.square_edges(row, col)
        top, bottom, left, right = sides

        # each corner dot of the square, with the 1's two sides that touch it
        corners = [
            ((row, col), top, left),                  # top-left
            ((row, col + 1), top, right),             # top-right
            ((row + 1, col), bottom, left),           # bottom-left
            ((row + 1, col + 1), bottom, right),      # bottom-right
        ]

        for (dot_row, dot_col), side_a, side_b in corners:
            outside = [e for e in board.dot_edges(dot_row, dot_col) if e not in sides]
            if all(board.get(e) == CROSS for e in outside):   # off-grid edges aren't listed
                why = (f"{describe_square(row, col)}: dead corner at {describe_dot(dot_row, dot_col)}, "
                       f"using both sides there would give the 1 two lines")
                result.cross(side_a, why)
                result.cross(side_b, why)


@rule(13, "Line Into a 1",
      "A line enters a 1's corner (directly or through a diagonal chain of 2s) -> cross the 1's far sides")
def line_into_a_1(board, result):
    """
    A line comes into a corner dot from outside and can't turn away (every
    other outside edge at that dot is crossed out or off the grid). That
    corner belongs either to:

      * a 1 directly, or
      * a 2 at the end of an unbroken diagonal chain of 2s leading to a 1

    Then the 1's only line is at the corner nearest the entering line, so
    cross out the 1's two FAR sides.

    Directly:                     Through a chain of 2s:

              │                         │
          + x +   +                 + x +   +   +   +
                1 x                       2
              + x +                     +   +   +   +
                                              2
                                        +   +   +   +
                                                  1 x
                                            +   + x +

    Why: the line goes along exactly ONE side of the first square at that
    corner. A 2 then has exactly one line at its opposite corner too, which
    is shared with the next square -- and a dot can't have just 1 line, so
    the next square also has exactly one side there. That carries down the
    chain to the 1, using up its only line at that corner.

    Flags a problem (via cross) if a far side is already a line.
    """
    for square in board.squares():
        for corner in CORNERS:
            lines, others = entering_lines(board, square, corner)
            if len(lines) != 1 or any(board.get(e) != CROSS for e in others):
                continue                                   # no line, or it could still turn away
            why = f"a line enters at {describe_dot(*corner_dot(*square, corner))} and can't turn away"
            one_line_enters(board, result, square, corner, why, clues=(1,))


@rule(14, "Line Into a 2",
      "A line enters a 2's corner (directly or through a chain of 2s), a far side is crossed -> fill the other")
def line_into_a_2(board, result):
    """
    Take a 2 with one of its two FAR sides crossed out. A LINE comes into
    the corner dot facing away from those far sides, from outside. That
    corner belongs either to:

      * the 2 itself, or
      * another 2 at the end of an unbroken diagonal chain of 2s leading
        to it

    Then:
      * the line can't turn away -- cross out the other outside edge(s)
        at the dot where it enters
      * fill the 2's other far side

    Directly:                     Through a chain of 2s:

              │                         │
          + x +   +                 + x +   +   +   +
                2 x                       2
              +───+                     +   +   +   +
                                              2
                                        +   +   +   +
                                                  2 x
                                            +   +───+

    Why: if the line turned away, the first square would have no line at
    that corner, so (through the chain) the last 2 would need both far
    sides -- but one is crossed. So the line goes along exactly ONE side
    of the first square; "exactly one" carries down the chain, so the last
    2 has exactly one far side: the open one.

    At the border there may be no outside edge to cross; the far side is
    still filled. Flags a problem if both far sides are crossed out.

    Also: if the line entering a 2 CAN'T turn away (the other outside edge
    is crossed, or off the grid), exactly one line leaves the 2 at its far
    corner -- so the two outside edges there (closest to the diagonal
    clue) are opposites. One filled -> cross the other; one crossed (or
    off the grid) -> fill the other. Works for every 2 down a chain too.

    And in the same case the 2's two FAR SIDES are opposites as well: if
    one far side is filled, the other is crossed out.

        before              after
              │                   │
          + x +   +           + x +   +
                2 │                 2 │
              +   +               + x +

        before                 after
              │                      │
          + x +   +   +          + x +   +   +
                2                      2
              +   + x +              +   + x +
                                         │
                  +   +                +   +
    """
    opposite_of = {corner: info["opposite"] for corner, info in CORNERS.items()}

    for square in board.squares():
        for corner in CORNERS:
            lines, others = entering_lines(board, square, corner)
            if len(lines) != 1:
                continue
            where = f"line at {describe_dot(*corner_dot(*square, corner))}"

            # every 2 this line heads into (directly, or down a chain of 2s)
            twos, _ = diagonal_path(board, square, corner)
            for two in twos:
                far_sides = corner_sides(board, *two, opposite_of[corner])
                crossed = board.count(far_sides, CROSS)
                if crossed == 0:
                    continue                               # nothing to go on for this 2
                if crossed == 1:
                    for edge in others:
                        result.cross(edge, f"{where} heads into the 2 at {describe_square(*two)}, "
                                           f"which has a far side crossed, so it can't turn away")
                one_line_reaches(board, result, two, corner, where)   # fills, or flags if both crossed

            # if the line can't turn away, each 2 on the way has exactly one
            # line at its far corner:
            if all(board.get(e) == CROSS for e in others):
                for two in twos:
                    why = f"{where} enters the 2 at {describe_square(*two)} and can't turn away"
                    # ... so the two outside edges there are opposites
                    one_line_out(board, result, two, opposite_of[corner], why)
                    # ... and so are its two far sides: one filled -> cross the other
                    far_a, far_b = corner_sides(board, *two, opposite_of[corner])
                    if board.get(far_a) == board.get(far_b) == LINE:
                        result.flag(f"{why}, but both of its far sides are filled")
                    elif board.get(far_a) == LINE:
                        result.cross(far_b, why + " and its other far side is filled")
                    elif board.get(far_b) == LINE:
                        result.cross(far_a, why + " and its other far side is filled")


@rule(15, "Next to 2s in a Corner",
      "A 2 with a dead corner, then a diagonal chain of 2s, ending at a 1 or a 3")
def next_to_2s_in_a_corner(board, result):
    """
    Start at a 2 with a DEAD corner (every outside edge at that dot is
    crossed out or off the grid). Walk diagonally away from that corner
    through any unbroken chain of 2s, to the first square that isn't a 2.

    Ends at a 1:  cross out the 1's two sides at the corner it shares
                  with the last 2.

        +   +   +   +        +   +   +   +
          2                    2
        +   +   +   +   ->   +   + x +   +
              1                  x 1
        +   +   +            +   +   +

    Ends at a 3:  every 2 (the corner one and the chain) gets its two sides
                  at the SAME corner as the dead one filled and its other
                  two sides crossed out; the 3 gets its two sides at the
                  corner it shares with the last 2 filled.

        +   +   +   +   +         +───+   +   +   +
          2                       │ 2 x
        +   +   +   +   +         + x +───+   +   +
              2            ->         │ 2 x
        +   +   +   +   +             + x +───+   +
                  3                       │ 3
        +   +   +   +                     +   +   +

    Why: at the dead corner the 2 has 0 or 2 lines, and each 2 along the
    chain passes "0 or 2" on to the next shared corner. A 1 can't have 2
    there, so it has 0. A 3 can't have 0 at any corner, so it has 2 --
    which pushes the last 2's lines to its far corner, and so on back up.

    Every 2 with a dead corner starts its own walk, in the direction away
    from that corner.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 2:
            continue

        for corner, info in CORNERS.items():
            # is this corner dead?
            outside = outside_edges(board, (row, col), corner)
            if not all(board.get(e) == CROSS for e in outside):
                continue

            # walk away from the dead corner (through the opposite corner)
            # along the chain of 2s
            opposite = info["opposite"]
            chain = square_and_2s_beyond(board, row, col, opposite)
            step_r, step_c = info["away"]
            end = (chain[-1][0] + step_r, chain[-1][1] + step_c)
            end_clue = clue_at(board, *end)

            what = "a 2" if len(chain) == 1 else f"a chain of {len(chain)} 2s"
            why = (f"{what} from {describe_square(row, col)} (dead {corner} corner) "
                   f"to the {end_clue} at {describe_square(*end)}") if end_clue is not None else ""

            if end_clue == 1:
                for edge in corner_sides(board, *end, corner):
                    result.cross(edge, why)

            elif end_clue == 3:
                for two in chain:
                    for edge in corner_sides(board, *two, corner):
                        result.fill(edge, why)
                    for edge in corner_sides(board, *two, info["opposite"]):
                        result.cross(edge, why + " (the 2 is complete)")
                for edge in corner_sides(board, *end, corner):
                    result.fill(edge, why)


@rule(16, "One's Crossed Corner",
      "A 1 with both sides at one corner crossed -> Line Into results for the square diagonally past it")
def ones_crossed_corner(board, result):
    """
    A 1 has both of its sides at one corner crossed out. Its only line is
    then one of its other two sides -- exactly one -- so exactly ONE line
    arrives at its opposite corner from the 1. That dot needs exactly one
    more line, through the square diagonally past it: just like a line
    entering that square's corner and not able to turn away.

    So walk diagonally past the opposite corner (through any chain of 2s)
    and apply the Line Into results:

      * a 2 with one far side crossed  -> fill its other far side
      * the first non-2 square is a 1  -> cross out its two far sides
      * the first non-2 square is a 3  -> fill its two far sides

        before                    after
        + x +   +   +             + x +   +   +
        x 1                       x 1
        +   +   +   +     ->      +   +   +   +
              3                         3 │
        +   +   +   +             +   +───+   +

    Also, whatever clue is diagonally past (or none): exactly one line
    leaves the 1's opposite corner through the two edges there closest to
    the 1, so they're opposites. One filled -> cross the other; one crossed
    (or off the grid) -> fill the other.

        before                    after
        + x +   +   +             + x +   +   +
        x 1                       x 1
        +   + x +   +     ->      +   + x +   +
                                      │
        +   +   +   +             +   +   +   +

    Flags a problem (via fill/cross) if an edge is already the opposite, or
    if a 2 along the way has both far sides crossed.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 1:
            continue

        for corner, info in CORNERS.items():
            if not all(board.get(e) == CROSS for e in corner_sides(board, row, col, corner)):
                continue
            why = f"{describe_square(row, col)} has its {corner} corner crossed out"

            # exactly one line leaves the 1 at its opposite corner ...
            # ... so the two edges there closest to the 1 are opposites
            one_line_out(board, result, (row, col), info["opposite"], why)

            # ... into the square diagonally past it, which it reaches at `corner`
            neighbour = diagonal_neighbour(row, col, info["opposite"])
            one_line_enters(board, result, neighbour, corner, why)


@rule(17, "Three's Filled Corner",
      "A 3 with both sides at one corner filled -> a 1 or 2s diagonally past its opposite corner")
def threes_filled_corner(board, result):
    """
    A 3 has both of its sides at one corner filled. Its missing side is one
    of its other two, so EXACTLY ONE line leaves the 3 at its opposite
    corner, into the square diagonally past it. Walk diagonally from there
    through any chain of 2s:

      * every 2 on the way gets exactly one line at its near corner, so
        exactly one at its far corner -- so exactly one line leaves through
        the OUTSIDE edges at its far corner: if one of those is filled,
        cross the other; if one is crossed (or off the grid), fill the other
      * a 1 at the end gets its two far sides crossed out

    A 2:                                A 1:

        +───+   +   +                       +───+   +   +
        │ 3                                 │ 3
        +   +   +   +                       +   +   +   +
              2                                   1 x
        +   +   + x +                       +   + x +
                  │
        +   +   +   +

    Also, at the 3's own opposite corner: exactly one line leaves through
    the two outside edges there, so they're opposites. One crossed (or off
    the grid) -> fill the other; one filled -> cross the other.

        before                after
        +   +───+             +   +───+
              3 │                   3 │
        +   +   +             +───+   +
            x                     x

    Flags a problem if both outside edges at one of those corners are
    already filled, or both crossed.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue

        for corner, info in CORNERS.items():
            if not all(board.get(e) == LINE for e in corner_sides(board, row, col, corner)):
                continue
            opposite = info["opposite"]
            why = f"{describe_square(row, col)} has its {corner} corner filled"

            # exactly one line leaves the 3 at its opposite corner ...
            # ... so the two outside edges there are opposites
            one_line_out(board, result, (row, col), opposite, why)

            # ... into the square diagonally past it, which it reaches at `corner`
            neighbour = diagonal_neighbour(row, col, opposite)

            # a 1 at the end of the walk (through any 2s): Line Into a 1
            one_line_enters(board, result, neighbour, corner, why, clues=(1,))

            # every 2 on the way: the outside edges at its far corner are opposites
            one_line_out_of_2s(board, result, neighbour, corner, why)


@rule(18, "Two Next to a Three",
      "A 2 (or chain of 2s) diagonal from a 3, a far side of a 2 crossed -> fill its other far side + the 3's far corner")
def two_next_to_a_three(board, result):
    """
    A 3 has a 2 touching it diagonally -- or an unbroken diagonal chain of
    2s going away from it. If one of a 2's FAR sides (the two at its corner
    pointing away from the 3) is crossed out:

      * fill that 2's other far side
      * fill the 3's far corner (its two sides at the corner pointing away
        from the 2s)

        before                    after
        +   +   +   +             +───+   +   +
        x 2                       x 2
        +   +   +   +             +   +   +   +
              3                         3 │
        +   +   +   +             +   +───+   +

    With a chain:

        before                    after
        +   +   +   +   +         +───+   +   +   +
        x 2                       x 2
        +   +   +   +   +         +   +   +   +   +
              2                         2
        +   +   +   +   +         +   +   +   +   +
                  3                         3 │
        +   +   +   +   +         +   +   +───+   +

    Why: the 3 has 1 or 2 lines at the corner it shares with the chain. If
    it had 2, the 2s along the chain would flip between 0 and 2 lines at
    their corners, and that 2 would need both its far sides -- but one is
    crossed. So the 3 has exactly one there, and "exactly one" carries
    along the chain: the 2 has exactly one far side (the open one), and the
    3's missing side touches the shared corner, so its far sides are lines.

    Flags a problem if both far sides of a 2 are crossed out.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue

        for corner, info in CORNERS.items():
            # the 2s going diagonally out from the 3 through `corner`; each
            # touches the previous one at its `opposite` corner, so its far
            # sides are the ones at `corner`
            opposite = info["opposite"]
            neighbour = diagonal_neighbour(row, col, corner)
            twos, _ = diagonal_path(board, neighbour, opposite)

            for distance, two in enumerate(twos, start=1):
                far_a, far_b = corner_sides(board, *two, corner)
                crossed = [e for e in (far_a, far_b) if board.get(e) == CROSS]
                if not crossed:
                    continue
                via = "" if distance == 1 else f" (through a chain of {distance} 2s)"
                why = (f"the 2 at {describe_square(*two)} has a far side crossed, next to "
                       f"the 3 at {describe_square(row, col)}{via}")
                if len(crossed) == 2:
                    result.flag(f"{why}, but both of its far sides are crossed out")
                    continue
                result.fill(far_b if crossed[0] == far_a else far_a, why)
                for edge in corner_sides(board, row, col, opposite):
                    result.fill(edge, why)


@rule(21, "One Next to a Three",
      "A 1 beside a 3, with the border or a crossed edge at one end of their shared side")
def one_next_to_a_three(board, result):
    """
    A 1 and a 3 share a side. At one end of that shared side, the dot's
    outward edge (pointing away from both squares) is crossed out or off
    the grid. Then:

      * fill the 3's side at that dot (the one along the border / crossed edge)
      * cross out the 1's two sides at its corner OPPOSITE that dot

        before                  after
        +   +   +   +           +   +───+   +
              3   1                   3   1 x
        +   +   +   +           +   +   + x +

    Why -- look at the shared side:
      * if it's a line, it's the 1's only line. At the dot, the shared side
        needs one more line; the 1's side there is empty, so it's the 3's.
      * if it's empty, the 3 has all its other sides, including the one at
        the dot. That line needs one more at the dot; the shared side is
        empty, so it's the 1's side there -- the 1's only line.
    Either way the 3's side at the dot is a line, and the 1's line touches
    that dot -- so its two sides at the opposite corner are empty.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue
        three = (row, col)
        top, bottom, left, right = board.square_edges(row, col)

        # each neighbour sharing a side with the 3, and that shared side
        for one, shared in (((row, col + 1), right), ((row, col - 1), left),
                            ((row + 1, col), bottom), ((row - 1, col), top)):
            if clue_at(board, *one) != 1:
                continue
            three_sides = board.square_edges(*three)
            one_sides = board.square_edges(*one)

            for dot in board.edge_ends(shared):
                # the dot's outward edge: not a side of the 3 or of the 1
                outward = [e for e in board.dot_edges(*dot) if e not in three_sides and e not in one_sides]
                if not all(board.get(e) == CROSS for e in outward):
                    continue                           # the line could still leave that way

                why = (f"the 1 at {describe_square(*one)} beside the 3 at {describe_square(*three)}, "
                       f"with no way out at {describe_dot(*dot)}")
                for edge in three_sides:
                    if edge != shared and dot in board.edge_ends(edge):
                        result.fill(edge, why)
                for edge in one_sides:
                    if dot not in board.edge_ends(edge):
                        result.cross(edge, why + " (the 1's line touches that dot)")


@rule(22, "Two Then Three",
      "A 2 with one side crossed and a 3 on its opposite side -> fill the 3's far side")
def two_then_three(board, result):
    """
    A 2 has one side crossed out, and a 3 shares the 2's OPPOSITE side --
    crossed side, 2 and 3 all in a line. Then the 3's far side (opposite
    the 2) is filled.

        before                after
        +   +   +   +         +   +   +   +
        x 2   3               x 2   3 │
        +   +   +   +         +   +   +   +

    Why: if the 3's far side were empty, the 3 would have its other three
    sides -- top, bottom and the side it shares with the 2. Then both ends
    of the shared side would already have 2 lines, so the 2's top and
    bottom would be empty. With its left crossed too, the 2 would have only
    1 line. Impossible -- so the 3's far side is a line.
    """
    for row, col in board.squares():
        if board.clue(row, col) != 2:
            continue
        top, bottom, left, right = board.square_edges(row, col)

        # (crossed side of the 2, the square on the opposite side)
        for crossed, three in ((left, (row, col + 1)), (right, (row, col - 1)),
                               (top, (row + 1, col)), (bottom, (row - 1, col))):
            if board.get(crossed) != CROSS or clue_at(board, *three) != 3:
                continue
            # the 3's far side: step once more in the same direction
            step_r, step_c = three[0] - row, three[1] - col
            three_top, three_bottom, three_left, three_right = board.square_edges(*three)
            far_side = {(0, 1): three_right, (0, -1): three_left,
                        (1, 0): three_bottom, (-1, 0): three_top}[(step_r, step_c)]
            result.fill(far_side, f"the 2 at {describe_square(row, col)} has a side crossed, "
                                  f"with the 3 at {describe_square(*three)} opposite it")


@rule(25, "Three With Two Ones",
      "A 3 with 1s on two sides that meet at a corner -> cross each 1's sides away from that corner")
def three_with_two_ones(board, result):
    """
    A 3 has a 1 sharing one of its sides, and another 1 sharing an
    ADJACENT side -- the two shared sides meet at one of the 3's corners.
    Then each 1's two sides that DON'T touch that corner are crossed out.

        before            after
        +   +   +         + x +   +
          1   3           x 1   3
        +   +   +         +   +   +
              1                 1 x
            +   +             + x +

    Why: the 3 misses only one side, so at least one of its two sides at
    that corner is a line. At that corner dot:
      * both are lines: each 1's line is the side it shares with the 3
      * only one is: that 1 is used up, the dot needs one more line, and
        the only way left is the OTHER 1's side at that dot
    Either way, each 1's only line touches that corner -- so its two sides
    away from it are empty.
    """
    step_to = {"top": (-1, 0), "bottom": (1, 0), "left": (0, -1), "right": (0, 1)}

    for row, col in board.squares():
        if board.clue(row, col) != 3:
            continue
        for corner, info in CORNERS.items():
            # the squares across the 3's two sides at this corner
            ones = [(row + step_to[side][0], col + step_to[side][1]) for side in info["sides"]]
            if not all(clue_at(board, *one) == 1 for one in ones):
                continue

            dot = corner_dot(row, col, corner)
            why = (f"the 3 at {describe_square(row, col)} has 1s on both sides of its {corner} "
                   f"corner, so each 1's line touches {describe_dot(*dot)}")
            for one in ones:
                for edge in board.square_edges(*one):
                    if dot not in board.edge_ends(edge):
                        result.cross(edge, why)
