"""Run with:  python3 -m unittest discover tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import verify
from board import CROSS, EMPTY, LINE, Board, Edge
from puzzle import decode_task, parse_grid_text
from rules import RULES, run_rule

RULE = {r.name: r for r in RULES}


def board_from(text):
    return Board(parse_grid_text(text))


class TestPuzzle(unittest.TestCase):
    def test_decode_5x5(self):
        p = decode_task("a32a33g03c2a3a213")
        self.assertEqual((p.width, p.height), (5, 5))
        self.assertEqual(p.clues[0], [None, 3, 2, None, 3])
        self.assertEqual(p.clues[4], [3, None, 2, 1, 3])

    def test_non_square_needs_size(self):
        with self.assertRaises(ValueError):
            decode_task("b")          # 2 squares: not a square grid
        p = decode_task("b", width=2, height=1)
        self.assertEqual(p.clues, [[None, None]])


class TestClueCheck(unittest.TestCase):
    def test_zero_crosses_all(self):
        b = board_from(". . .\n. 0 .\n. . .")
        result = run_rule(RULE["Clue Check"], b)
        self.assertEqual(len(result.changes), 4)
        self.assertTrue(all(c.new_state == CROSS for c in result.changes))

    def test_satisfied_crosses_rest(self):
        b = board_from("2")
        b.set(Edge("H", 0, 0), LINE)
        b.set(Edge("V", 0, 0), LINE)
        result = run_rule(RULE["Clue Check"], b)
        self.assertEqual({c.edge for c in result.changes}, {Edge("H", 1, 0), Edge("V", 0, 1)})
        self.assertTrue(all(c.new_state == CROSS for c in result.changes))

    def test_needs_all_fills(self):
        b = board_from("3")
        b.set(Edge("H", 0, 0), CROSS)
        result = run_rule(RULE["Clue Check"], b)
        self.assertEqual(len(result.changes), 3)
        self.assertTrue(all(c.new_state == LINE for c in result.changes))

    def test_flags_too_many_lines(self):
        b = board_from("1")
        b.set(Edge("H", 0, 0), LINE)
        b.set(Edge("H", 1, 0), LINE)
        self.assertEqual(len(run_rule(RULE["Clue Check"], b).problems), 1)


class TestContinueLine(unittest.TestCase):
    def test_corner_dot_continues(self):
        # top-left dot (0,0) only has a right edge and a down edge
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 0), LINE)
        result = run_rule(RULE["Continue Line"], b)
        self.assertIn(Edge("V", 0, 0), [c.edge for c in result.changes])

    def test_two_ways_out_does_nothing(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 0), LINE)   # reaches dot (0,1): can go right or down
        result = run_rule(RULE["Continue Line"], b)
        self.assertNotIn(Edge("H", 0, 1), [c.edge for c in result.changes])

    def test_flags_dead_end(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 0), LINE)
        b.set(Edge("V", 0, 0), CROSS)
        self.assertEqual(len(run_rule(RULE["Continue Line"], b).problems), 1)


class TestAdjacentThrees(unittest.TestCase):
    def test_side_by_side(self):
        b = board_from(". . .\n3 3 .\n. . .")
        result = run_rule(RULE["Adjacent Threes"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {
            Edge("V", 1, 0): LINE, Edge("V", 1, 1): LINE, Edge("V", 1, 2): LINE,
            Edge("V", 0, 1): CROSS, Edge("V", 2, 1): CROSS,
        })

    def test_stacked_at_border(self):
        b = board_from("3 .\n3 .")       # left column: no edge to cross on the left
        result = run_rule(RULE["Adjacent Threes"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE, Edge("H", 1, 0): LINE, Edge("H", 2, 0): LINE,
            Edge("H", 1, 1): CROSS,
        })

    def test_chain_of_three_has_no_problems(self):
        b = board_from("3 3 3")
        self.assertEqual(run_rule(RULE["Adjacent Threes"], b).problems, [])


class TestThreeInACorner(unittest.TestCase):
    def test_grid_corner(self):
        b = board_from("3 .\n. .")           # 3 in the top-left grid corner
        result = run_rule(RULE["Three in a Corner"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE})

    def test_middle_with_crosses(self):
        b = board_from(". . .\n. 3 .\n. . .")
        b.set(Edge("V", 0, 1), CROSS)        # edge above the 3's top-left dot
        b.set(Edge("H", 1, 0), CROSS)        # edge left of the 3's top-left dot
        result = run_rule(RULE["Three in a Corner"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("H", 1, 1): LINE, Edge("V", 1, 1): LINE})

    def test_one_way_out_does_nothing(self):
        b = board_from(". . .\n. 3 .\n. . .")
        b.set(Edge("V", 0, 1), CROSS)        # only one of the two outside edges crossed
        self.assertEqual(run_rule(RULE["Three in a Corner"], b).changes, [])

    def test_flags_if_side_already_crossed(self):
        b = board_from("3 .\n. .")
        b.set(Edge("H", 0, 0), CROSS)
        self.assertEqual(len(run_rule(RULE["Three in a Corner"], b).problems), 1)


class TestDiagonalThrees(unittest.TestCase):
    def changes(self, text):
        b = board_from(text)
        result = run_rule(RULE["Diagonal Threes"], b)
        self.assertEqual(result.problems, [])
        return {c.edge: c.new_state for c in result.changes}

    def test_down_right_pair(self):
        got = self.changes("3 .\n. 3")
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE,     # top-left 3: top + left
            Edge("H", 2, 1): LINE, Edge("V", 1, 2): LINE,     # bottom-right 3: bottom + right
        })

    def test_down_left_pair(self):
        got = self.changes(". 3\n3 .")
        self.assertEqual(got, {
            Edge("H", 0, 1): LINE, Edge("V", 0, 2): LINE,     # top-right 3: top + right
            Edge("H", 2, 0): LINE, Edge("V", 1, 0): LINE,     # bottom-left 3: bottom + left
        })

    def test_line_of_three_only_fills_ends(self):
        got = self.changes("3 . .\n. 3 .\n. . 3")
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE,
            Edge("H", 3, 2): LINE, Edge("V", 2, 3): LINE,
        })

    def test_single_three_does_nothing(self):
        self.assertEqual(self.changes(". . .\n. 3 .\n. . ."), {})

    def test_crosses_away_from_corners_in_middle(self):
        got = self.changes(". . . .\n. 3 . .\n. . 3 .\n. . . .")
        self.assertEqual(got, {
            Edge("H", 1, 1): LINE, Edge("V", 1, 1): LINE,     # first 3: top + left
            Edge("V", 0, 1): CROSS, Edge("H", 1, 0): CROSS,   # away from dot (1,1)
            Edge("H", 3, 2): LINE, Edge("V", 2, 3): LINE,     # last 3: bottom + right
            Edge("V", 3, 3): CROSS, Edge("H", 3, 3): CROSS,   # away from dot (3,3)
        })

    def test_3_2_3(self):
        got = self.changes("3 . .\n. 2 .\n. . 3")
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE,     # first 3: top + left
            Edge("H", 3, 2): LINE, Edge("V", 2, 3): LINE,     # last 3: bottom + right
        })

    def test_3_2_2_3_down_left(self):
        got = self.changes(". . . 3\n. . 2 .\n. 2 . .\n3 . . .")
        self.assertEqual(got, {
            Edge("H", 0, 3): LINE, Edge("V", 0, 4): LINE,     # first 3: top + right
            Edge("H", 4, 0): LINE, Edge("V", 3, 0): LINE,     # last 3: bottom + left
        })

    def test_2s_then_blank_does_nothing(self):
        self.assertEqual(self.changes("3 . .\n. 2 .\n. . ."), {})


class TestLineIntoA3(unittest.TestCase):
    def test_line_enters_from_above(self):
        b = board_from(". . .\n. 3 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)          # line coming down into the 3's top-left dot
        result = run_rule(RULE["Line Into a 3"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {
            Edge("H", 1, 0): CROSS,               # can't turn left
            Edge("H", 2, 1): LINE,                # far side: bottom
            Edge("V", 1, 2): LINE,                # far side: right
        })

    def test_border_has_nothing_to_cross(self):
        b = board_from("3 .\n. .")
        b.set(Edge("H", 0, 1), LINE)          # line along top border into top-right dot
        result = run_rule(RULE["Line Into a 3"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("H", 1, 0): LINE, Edge("V", 0, 0): LINE})

    def test_flags_turn_at_corner(self):
        b = board_from(". . .\n. 3 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)
        b.set(Edge("H", 1, 0), LINE)
        self.assertEqual(len(run_rule(RULE["Line Into a 3"], b).problems), 1)


class TestLineIntoA3ThroughChain(unittest.TestCase):
    def test_through_chain_of_2s(self):
        b = board_from(". . . . .\n. 2 . . .\n. . 2 . .\n. . . 3 .\n. . . . .")
        b.set(Edge("V", 0, 1), LINE)          # line comes down into the first 2's top-left dot
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 3"], b).changes}
        self.assertEqual(got, {
            Edge("H", 1, 0): CROSS,               # can't turn left at the entering dot
            Edge("H", 4, 3): LINE,                # 3's bottom
            Edge("V", 3, 4): LINE,                # 3's right
        })

    def test_chain_broken_does_nothing(self):
        b = board_from(". . . . .\n. 2 . . .\n. . . . .\n. . . 3 .\n. . . . .")
        b.set(Edge("V", 0, 1), LINE)
        self.assertEqual(run_rule(RULE["Line Into a 3"], b).changes, [])


class TestFullDot(unittest.TestCase):
    # dot (1, 1) is the middle dot of a 2x2 grid; it touches 4 edges
    def test_corner(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 1, 0), LINE)         # from the left
        b.set(Edge("V", 1, 1), LINE)         # going down
        result = run_rule(RULE["Full Dot"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("V", 0, 1): CROSS, Edge("H", 1, 1): CROSS})

    def test_straight(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 1, 0), LINE)
        b.set(Edge("H", 1, 1), LINE)
        result = run_rule(RULE["Full Dot"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("V", 0, 1): CROSS, Edge("V", 1, 1): CROSS})

    def test_one_line_does_nothing(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 1, 0), LINE)
        self.assertEqual(run_rule(RULE["Full Dot"], b).changes, [])

    def test_flags_branch(self):
        b = board_from(". .\n. .")
        for e in (Edge("H", 1, 0), Edge("H", 1, 1), Edge("V", 1, 1)):
            b.set(e, LINE)
        self.assertEqual(len(run_rule(RULE["Full Dot"], b).problems), 1)


class TestNoSelfLoop(unittest.TestCase):
    def u_shape(self, text):
        """Draw a U around the top-left square: left, top, right sides."""
        b = board_from(text)
        for e in (Edge("V", 0, 0), Edge("H", 0, 0), Edge("V", 0, 1)):
            b.set(e, LINE)
        return b

    def test_crosses_closing_edge(self):
        b = self.u_shape(". .\n. 2")       # closing would leave the 2 with no lines
        result = run_rule(RULE["No Self Loop"], b)
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {Edge("H", 1, 0): CROSS})

    def test_crosses_when_other_lines_exist(self):
        b = self.u_shape(". .\n. .")
        b.set(Edge("H", 2, 1), LINE)       # another piece of line elsewhere
        got = {c.edge: c.new_state for c in run_rule(RULE["No Self Loop"], b).changes}
        self.assertEqual(got, {Edge("H", 1, 0): CROSS})

    def test_leaves_it_when_closing_is_the_answer(self):
        b = self.u_shape(". .\n. .")       # no clues, no other lines: closing = a full answer
        self.assertEqual(run_rule(RULE["No Self Loop"], b).changes, [])

    def test_ends_far_apart_do_nothing(self):
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 0), LINE)
        b.set(Edge("H", 0, 1), LINE)       # straight line: ends 2 dots apart
        self.assertEqual(run_rule(RULE["No Self Loop"], b).changes, [])


class TestNoDeadEnds(unittest.TestCase):
    def test_middle_dot(self):
        b = board_from(". .\n. .")             # middle dot (1, 1) has 4 edges
        for e in (Edge("V", 0, 1), Edge("H", 1, 0), Edge("H", 1, 1)):
            b.set(e, CROSS)
        got = {c.edge: c.new_state for c in run_rule(RULE["No Dead Ends"], b).changes}
        self.assertEqual(got, {Edge("V", 1, 1): CROSS})

    def test_border_dot(self):
        b = board_from(". .\n. .")             # top-middle dot (0, 1) has 3 edges
        b.set(Edge("H", 0, 0), CROSS)
        b.set(Edge("H", 0, 1), CROSS)
        got = {c.edge: c.new_state for c in run_rule(RULE["No Dead Ends"], b).changes}
        # the top-middle dot, plus both top corner dots (now each down to 1 edge)
        self.assertEqual(got, {Edge("V", 0, 1): CROSS, Edge("V", 0, 0): CROSS, Edge("V", 0, 2): CROSS})

    def test_two_open_edges_do_nothing(self):
        b = board_from(". .\n. .")
        b.set(Edge("V", 0, 1), CROSS)
        b.set(Edge("H", 1, 0), CROSS)
        self.assertNotIn(Edge("V", 1, 1), [c.edge for c in run_rule(RULE["No Dead Ends"], b).changes])


class TestTwoInACorner(unittest.TestCase):
    def test_grid_corner_with_far_side_crossed(self):
        b = board_from("2 .\n. .")             # top-left grid corner is dead already
        b.set(Edge("V", 0, 1), CROSS)          # far side: right
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE,   # top + left filled
            Edge("H", 1, 0): CROSS,                         # bottom crossed (right already was)
            Edge("H", 0, 1): LINE, Edge("V", 1, 0): LINE,   # (c) only way out at the side corners
        })

    def test_middle_dead_corner(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), CROSS)          # outside edges at the 2's top-left dot
        b.set(Edge("H", 1, 0), CROSS)
        b.set(Edge("H", 2, 1), CROSS)          # far side: bottom
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {
            Edge("H", 1, 1): LINE, Edge("V", 1, 1): LINE,
            Edge("V", 1, 2): CROSS,
        })

    def test_grid_corner_2_fills_next_border_edges(self):
        # no far side crossed, so (a) does nothing -- but (c): exactly one line
        # leaves each side corner, and on the border the only way out is
        # along the border
        b = board_from("2 .\n. .")
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 0, 1): LINE, Edge("V", 1, 0): LINE})

    def test_flags_if_corner_side_crossed(self):
        b = board_from("2 .\n. .")
        b.set(Edge("V", 0, 1), CROSS)
        b.set(Edge("H", 0, 0), CROSS)
        self.assertTrue(run_rule(RULE["Two in a Corner"], b).problems)

    def test_opposite_corner_outside_edges_match(self):
        b = board_from("2 .\n. .")             # dead top-left grid corner
        b.set(Edge("H", 1, 1), CROSS)          # outside edge going right from the middle dot
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("V", 1, 1)), CROSS)   # outside edge going down

    def test_opposite_corner_one_filled(self):
        # like the screenshot: 2 with a dead top-right corner, edge going down
        # from its bottom-left dot filled -> edge going left filled too
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 2), CROSS)          # outside edges at the 2's top-right dot (1, 2)
        b.set(Edge("H", 1, 2), CROSS)
        b.set(Edge("V", 2, 1), LINE)           # edge going down from its bottom-left dot (2, 1)
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 2, 0): LINE})

    def test_opposite_corner_through_chain(self):
        b = board_from("2 . .\n. 2 .\n. . .")  # dead corner 2, then a 2 diagonally
        b.set(Edge("H", 2, 2), CROSS)          # outside edge right of dot (2,2)
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("V", 2, 2)), CROSS)   # outside edge below dot (2,2)

    def test_dead_corner_from_one_cross_and_the_border(self):
        b = board_from(". 2 .\n. . .")         # 2 on the top border
        b.set(Edge("H", 0, 0), CROSS)          # its top-left dot: edge to the left crossed, nothing above
        b.set(Edge("V", 0, 2), CROSS)          # far side: right
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {
            Edge("H", 0, 1): LINE, Edge("V", 0, 1): LINE,   # top + left filled
            Edge("H", 1, 1): CROSS,                         # bottom crossed
            Edge("H", 0, 2): LINE,                          # (c) only way out at the top-right corner
        })

    def test_side_corner_only_way_out_on_border(self):
        # like the screenshot: 2 on the left border with a dead top-left corner
        b = board_from(". .\n2 .\n. .")
        b.set(Edge("V", 0, 0), CROSS)          # edge above the 2's top-left dot (1, 0)
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("V", 2, 0)), LINE)   # left edge of the row below

    def test_off_diagonal_2_far_corner(self):
        # like the screenshot: 2 at (2, 2) with a dead top-right corner; the 2
        # diagonally past its top-left corner gets exactly one line, so at
        # THAT 2's far corner one crossed edge means the other is filled
        b = board_from(". . . .\n. 2 . .\n. . 2 .\n. . . .")
        b.set(Edge("V", 1, 3), CROSS)          # outside edges at (2, 2)'s top-right dot (2, 3)
        b.set(Edge("H", 2, 3), CROSS)
        b.set(Edge("H", 1, 0), CROSS)          # at (1, 1)'s top-left dot: edge going left crossed
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("V", 0, 1)), LINE)   # so the edge going up is filled

    def test_side_corners_of_chain_2s(self):
        # 2 in the grid corner, then a 2 diagonally: the chain 2's side
        # corners get the same treatment
        b = board_from("2 . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 2), CROSS)          # at (1, 1)'s top-right dot (1, 2): edge going up crossed
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("H", 1, 2)), LINE)   # so the edge going right is filled

    def test_side_corner_one_filled_crosses_the_other(self):
        # like the screenshot: 2 with a dead bottom-right corner, a line coming
        # in from the left at its bottom-left dot -> the edge going down is crossed
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("H", 2, 2), CROSS)          # outside edges at the 2's bottom-right dot (2, 2)
        b.set(Edge("V", 2, 2), CROSS)
        b.set(Edge("H", 2, 0), LINE)           # line coming in from the left at dot (2, 1)
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {Edge("V", 2, 1): CROSS})

    def test_side_corner_two_ways_out_does_nothing(self):
        b = self.dead_top_left_2(". . .\n. 2 .\n. . .")
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {})              # side corners each have 2 open outside edges

    def test_opposite_corner_on_border(self):
        # 2 on the left border with a dead top-right corner. Its opposite
        # corner, dot (2, 0), is on the left border: the outside edge going
        # left doesn't exist, so the one going down gets crossed.
        b = board_from(". .\n2 .\n. .")
        b.set(Edge("V", 0, 1), CROSS)          # outside edges at the 2's top-right dot (1, 1)
        b.set(Edge("H", 1, 1), CROSS)
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got.get(Edge("V", 2, 0)), CROSS)

    def test_opposite_corner_on_border_already_crossed(self):
        b = board_from("2\n.")                 # the only outside edge there is already crossed
        b.set(Edge("V", 1, 1), CROSS)
        self.assertNotIn(Edge("V", 1, 1), [c.edge for c in run_rule(RULE["Two in a Corner"], b).changes])

    def dead_top_left_2(self, text):
        """3x3 board with a 2 in the middle whose top-left corner is dead."""
        b = board_from(text)
        b.set(Edge("V", 0, 1), CROSS)          # outside edges at the 2's top-left dot (1, 1)
        b.set(Edge("H", 1, 0), CROSS)
        return b

    def test_side_corner_line_into_3(self):
        b = self.dead_top_left_2(". . 3\n. 2 .\n. . .")   # 3 diagonally past the 2's top-right
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 0, 2): LINE, Edge("V", 0, 3): LINE})   # 3's top + right

    def test_side_corner_line_into_1(self):
        b = self.dead_top_left_2(". . .\n. 2 .\n1 . .")   # 1 diagonally past the 2's bottom-left
        got = {c.edge: c.new_state for c in run_rule(RULE["Two in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 3, 0): CROSS, Edge("V", 2, 0): CROSS})  # 1's bottom + left


class TestDiagonalLinesIntoA2(unittest.TestCase):
    RULE_NAME = "Diagonal Lines Into a 2"

    def test_single_two(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)            # down into the 2's top-left dot (1,1)
        b.set(Edge("V", 2, 2), LINE)            # up into the 2's bottom-right dot (2,2)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 1, 0): CROSS, Edge("H", 2, 2): CROSS})

    def test_other_diagonal(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 2), LINE)            # down into top-right dot (1,2)
        b.set(Edge("V", 2, 1), LINE)            # up into bottom-left dot (2,1)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 1, 2): CROSS, Edge("H", 2, 0): CROSS})

    def test_chain_of_two(self):
        b = board_from(". . . .\n. 2 . .\n. . 2 .\n. . . .")
        b.set(Edge("V", 0, 1), LINE)            # into top-left dot (1,1) of the first 2
        b.set(Edge("V", 3, 3), LINE)            # into bottom-right dot (3,3) of the last 2
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 1, 0): CROSS, Edge("H", 3, 3): CROSS})

    def test_only_one_corner_does_nothing(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)
        self.assertEqual(run_rule(RULE[self.RULE_NAME], b).changes, [])


class TestOneInACorner(unittest.TestCase):
    def test_grid_corner(self):
        b = board_from("1 .\n. .")             # 1 in the top-left grid corner
        got = {c.edge: c.new_state for c in run_rule(RULE["One in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 0, 0): CROSS, Edge("V", 0, 0): CROSS})

    def test_middle_dead_corner(self):
        b = board_from(". . .\n. 1 .\n. . .")
        b.set(Edge("V", 0, 1), CROSS)          # outside edges at the 1's top-left dot
        b.set(Edge("H", 1, 0), CROSS)
        got = {c.edge: c.new_state for c in run_rule(RULE["One in a Corner"], b).changes}
        self.assertEqual(got, {Edge("H", 1, 1): CROSS, Edge("V", 1, 1): CROSS})

    def test_open_corner_does_nothing(self):
        b = board_from(". . .\n. 1 .\n. . .")
        b.set(Edge("V", 0, 1), CROSS)          # only one outside edge crossed
        self.assertEqual(run_rule(RULE["One in a Corner"], b).changes, [])

    def test_flags_if_side_is_a_line(self):
        b = board_from("1 .\n. .")
        b.set(Edge("H", 0, 0), LINE)
        self.assertTrue(run_rule(RULE["One in a Corner"], b).problems)


class TestLineIntoA1(unittest.TestCase):
    def test_line_from_above_cant_turn(self):
        b = board_from(". . .\n. 1 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)           # line comes down into the 1's top-left dot
        b.set(Edge("H", 1, 0), CROSS)          # can't turn left
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 1"], b).changes}
        self.assertEqual(got, {Edge("H", 2, 1): CROSS, Edge("V", 1, 2): CROSS})

    def test_border_line(self):
        b = board_from(". 1\n. .")              # 1 on the top border
        b.set(Edge("H", 0, 0), LINE)           # line along the border into its top-left dot
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 1"], b).changes}
        self.assertEqual(got, {Edge("H", 1, 1): CROSS, Edge("V", 0, 2): CROSS})

    def test_can_still_turn_away_does_nothing(self):
        b = board_from(". . .\n. 1 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)           # other outside edge still open
        self.assertEqual(run_rule(RULE["Line Into a 1"], b).changes, [])

    def test_through_chain_of_2s(self):
        b = board_from(". . . . .\n. 2 . . .\n. . 2 . .\n. . . 1 .\n. . . . .")
        b.set(Edge("V", 0, 1), LINE)           # line comes down into the first 2's top-left dot
        b.set(Edge("H", 1, 0), CROSS)          # can't turn left
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 1"], b).changes}
        self.assertEqual(got, {Edge("H", 4, 3): CROSS, Edge("V", 3, 4): CROSS})   # 1's bottom + right

    def test_chain_broken_by_blank_does_nothing(self):
        b = board_from(". . . . .\n. 2 . . .\n. . . . .\n. . . 1 .\n. . . . .")
        b.set(Edge("V", 0, 1), LINE)
        b.set(Edge("H", 1, 0), CROSS)
        self.assertEqual(run_rule(RULE["Line Into a 1"], b).changes, [])


class TestLineIntoA2(unittest.TestCase):
    def test_line_from_above_right_side_crossed(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)           # line comes down into the 2's top-left dot
        b.set(Edge("V", 1, 2), CROSS)          # the 2's right side (a far side) is crossed
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {Edge("H", 1, 0): CROSS, Edge("H", 2, 1): LINE})

    def test_border_just_fills(self):
        b = board_from(". 2\n. .")              # 2 on the top border
        b.set(Edge("H", 0, 0), LINE)           # line along the border into its top-left dot
        b.set(Edge("H", 1, 1), CROSS)          # bottom (far side) crossed
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {
            Edge("V", 0, 2): LINE,                # the 2's right (the open far side)
            Edge("V", 1, 2): LINE,                # only way out at its far corner (border)
        })

    def test_no_far_side_crossed_does_nothing(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)
        self.assertEqual(run_rule(RULE["Line Into a 2"], b).changes, [])

    def test_flags_both_far_sides_crossed(self):
        b = board_from(". . .\n. 2 .\n. . .")
        b.set(Edge("V", 0, 1), LINE)
        b.set(Edge("V", 1, 2), CROSS)
        b.set(Edge("H", 2, 1), CROSS)
        self.assertTrue(run_rule(RULE["Line Into a 2"], b).problems)

    def test_through_chain_of_2s(self):
        b = board_from(". . . . .\n. 2 . . .\n. . 2 . .\n. . . 2 .\n. . . . .")
        b.set(Edge("V", 0, 1), LINE)          # line comes down into the first 2's top-left dot
        b.set(Edge("V", 3, 4), CROSS)         # last 2's right side (a far side) is crossed
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {
            Edge("H", 1, 0): CROSS,               # can't turn left at the entering dot
            Edge("H", 4, 3): LINE,                # last 2's bottom (the open far side)
        })

    # line can't turn away -> the edges at the 2's far corner are opposites
    def can_not_turn_board(self, text):
        b = board_from(text)
        b.set(Edge("V", 0, 1), LINE)          # line comes down into the 2's top-left dot (1, 1)
        b.set(Edge("H", 1, 0), CROSS)         # can't turn left
        return b

    def test_far_corner_one_crossed(self):
        b = self.can_not_turn_board(". . . .\n. 2 . .\n. . . .\n. . . .")
        b.set(Edge("H", 2, 2), CROSS)         # edge going right from the far dot (2, 2)
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {Edge("V", 2, 2): LINE})   # edge going down

    def test_far_corner_one_filled(self):
        b = self.can_not_turn_board(". . . .\n. 2 . .\n. . . .\n. . . .")
        b.set(Edge("V", 2, 2), LINE)
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {Edge("H", 2, 2): CROSS})

    def test_far_corner_could_turn_away_does_nothing(self):
        b = board_from(". . . .\n. 2 . .\n. . . .\n. . . .")
        b.set(Edge("V", 0, 1), LINE)          # the edge to the left is still open
        b.set(Edge("H", 2, 2), CROSS)
        self.assertEqual(run_rule(RULE["Line Into a 2"], b).changes, [])

    def test_far_side_filled_crosses_the_other(self):
        b = self.can_not_turn_board(". . . .\n. 2 . .\n. . . .\n. . . .")
        b.set(Edge("V", 1, 2), LINE)          # the 2's right side (a far side) is filled
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got, {Edge("H", 2, 1): CROSS})   # so its bottom is crossed

    def test_far_side_filled_but_could_turn_away_does_nothing(self):
        b = board_from(". . . .\n. 2 . .\n. . . .\n. . . .")
        b.set(Edge("V", 0, 1), LINE)          # line comes in, but the edge to the left is open
        b.set(Edge("V", 1, 2), LINE)
        self.assertEqual(run_rule(RULE["Line Into a 2"], b).changes, [])

    def test_far_corner_through_chain(self):
        b = self.can_not_turn_board(". . . .\n. 2 . .\n. . 2 .\n. . . .")
        b.set(Edge("H", 3, 3), CROSS)         # edge going right from the last 2's far dot (3, 3)
        got = {c.edge: c.new_state for c in run_rule(RULE["Line Into a 2"], b).changes}
        self.assertEqual(got.get(Edge("V", 3, 3)), LINE)


class TestNextTo2sInACorner(unittest.TestCase):
    RULE_NAME = "Next to 2s in a Corner"

    def changes(self, b):
        result = run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(result.problems, [])
        return {c.edge: c.new_state for c in result.changes}

    def test_2_then_1(self):
        b = board_from("2 . .\n. 1 .\n. . .")   # 2 in the top-left grid corner
        self.assertEqual(self.changes(b), {Edge("H", 1, 1): CROSS, Edge("V", 1, 1): CROSS})

    def test_chain_then_1(self):
        b = board_from("2 . .\n. 2 .\n. . 1")
        self.assertEqual(self.changes(b), {Edge("H", 2, 2): CROSS, Edge("V", 2, 2): CROSS})

    def test_chain_then_3(self):
        b = board_from("2 . . .\n. 2 . .\n. . 3 .\n. . . .")
        self.assertEqual(self.changes(b), {
            # corner 2: top + left filled, bottom + right crossed
            Edge("H", 0, 0): LINE, Edge("V", 0, 0): LINE,
            Edge("H", 1, 0): CROSS, Edge("V", 0, 1): CROSS,
            # middle 2: top + left filled, bottom + right crossed
            Edge("H", 1, 1): LINE, Edge("V", 1, 1): LINE,
            Edge("H", 2, 1): CROSS, Edge("V", 1, 2): CROSS,
            # the 3: top + left filled
            Edge("H", 2, 2): LINE, Edge("V", 2, 2): LINE,
        })

    def test_dead_corner_in_middle(self):
        b = board_from(". . . .\n. 2 . .\n. . 1 .\n. . . .")
        b.set(Edge("V", 0, 1), CROSS)            # outside edges at the 2's top-left dot
        b.set(Edge("H", 1, 0), CROSS)
        self.assertEqual(self.changes(b), {Edge("H", 2, 2): CROSS, Edge("V", 2, 2): CROSS})

    def test_ends_at_blank_does_nothing(self):
        b = board_from("2 . .\n. . .\n. . 1")
        self.assertEqual(self.changes(b), {})


class TestOnesCrossedCorner(unittest.TestCase):
    RULE_NAME = "One's Crossed Corner"

    def changes(self, text, crossed):
        b = board_from(text)
        for e in crossed:
            b.set(e, CROSS)
        result = run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(result.problems, [])
        return {c.edge: c.new_state for c in result.changes}

    # the 1 is at (0, 0); its top and left are crossed
    TOP_LEFT_CROSSED = [Edge("H", 0, 0), Edge("V", 0, 0)]

    def test_then_3(self):
        got = self.changes("1 .\n. 3", self.TOP_LEFT_CROSSED)
        self.assertEqual(got, {Edge("H", 2, 1): LINE, Edge("V", 1, 2): LINE})   # 3's bottom + right

    def test_then_1(self):
        got = self.changes("1 .\n. 1", self.TOP_LEFT_CROSSED)
        self.assertEqual(got, {Edge("H", 2, 1): CROSS, Edge("V", 1, 2): CROSS})

    def test_then_2_with_far_side_crossed(self):
        got = self.changes("1 .\n. 2", self.TOP_LEFT_CROSSED + [Edge("V", 1, 2)])
        self.assertEqual(got, {Edge("H", 2, 1): LINE})                          # 2's bottom

    def test_through_chain_of_2s_to_3(self):
        got = self.changes("1 . .\n. 2 .\n. . 3", self.TOP_LEFT_CROSSED)
        self.assertEqual(got, {Edge("H", 3, 2): LINE, Edge("V", 2, 3): LINE})

    def test_only_one_side_crossed_does_nothing(self):
        got = self.changes("1 .\n. 3", [Edge("H", 0, 0)])
        self.assertEqual(got, {})

    # edges closest to the 1 at its opposite corner, dot (1, 1)
    def test_closest_edges_one_crossed(self):
        got = self.changes("1 . .\n. . .\n. . .", self.TOP_LEFT_CROSSED + [Edge("H", 1, 1)])
        self.assertEqual(got, {Edge("V", 1, 1): LINE})

    def test_closest_edges_one_filled(self):
        b = board_from("1 . .\n. . .\n. . .")
        for e in self.TOP_LEFT_CROSSED:
            b.set(e, CROSS)
        b.set(Edge("V", 1, 1), LINE)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 1, 1): CROSS})

    def test_closest_edges_on_border(self):
        got = self.changes("1\n.", self.TOP_LEFT_CROSSED)   # only one edge there: going down
        self.assertEqual(got, {Edge("V", 1, 1): LINE})


class TestThreesFilledCorner(unittest.TestCase):
    RULE_NAME = "Three's Filled Corner"

    def changes(self, text, filled=(), crossed=()):
        b = board_from(text)
        b.set(Edge("H", 0, 0), LINE)           # the 3 at (0, 0): top + left filled
        b.set(Edge("V", 0, 0), LINE)
        for e in filled:
            b.set(e, LINE)
        for e in crossed:
            b.set(e, CROSS)
        result = run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(result.problems, [])
        return {c.edge: c.new_state for c in result.changes}

    def test_then_1(self):
        got = self.changes("3 . .\n. 1 .\n. . .")
        self.assertEqual(got, {Edge("H", 2, 1): CROSS, Edge("V", 1, 2): CROSS})   # 1's bottom + right

    def test_then_2_one_crossed(self):
        got = self.changes("3 . .\n. 2 .\n. . .", crossed=[Edge("H", 2, 2)])   # edge going right
        self.assertEqual(got, {Edge("V", 2, 2): LINE})                            # edge going down

    def test_then_2_one_filled(self):
        got = self.changes("3 . .\n. 2 .\n. . .", filled=[Edge("V", 2, 2)])    # edge going down
        self.assertEqual(got, {Edge("H", 2, 2): CROSS})                           # edge going right

    def test_then_2_on_border(self):
        got = self.changes("3 .\n. 2")         # 2's far corner is the grid corner: no outside edges
        self.assertEqual(got, {})

    def test_through_chain_of_2s_to_1(self):
        got = self.changes("3 . . .\n. 2 . .\n. . 1 .\n. . . .")
        self.assertEqual(got, {Edge("H", 3, 2): CROSS, Edge("V", 2, 3): CROSS})

    def test_through_chain_last_2(self):
        got = self.changes("3 . . .\n. 2 . .\n. . 2 .\n. . . .", crossed=[Edge("H", 3, 3)])
        self.assertEqual(got, {Edge("V", 3, 3): LINE})

    def test_corner_not_filled_does_nothing(self):
        b = board_from("3 . .\n. 1 .\n. . .")
        b.set(Edge("H", 0, 0), LINE)           # only the top
        self.assertEqual(run_rule(RULE[self.RULE_NAME], b).changes, [])

    def test_own_opposite_corner_one_crossed(self):
        # like the screenshot: 3 with its top + right filled, 1 below it
        b = board_from(". 3 .\n. 1 .")
        b.set(Edge("H", 0, 1), LINE)           # 3's top
        b.set(Edge("V", 0, 2), LINE)           # 3's right
        b.set(Edge("V", 1, 1), CROSS)          # edge going down from the 3's bottom-left dot (1, 1)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 1, 0): LINE})   # edge going left from that dot

    def test_own_opposite_corner_one_filled(self):
        b = board_from(". 3 .\n. . .\n. . .")
        b.set(Edge("H", 0, 1), LINE)
        b.set(Edge("V", 0, 2), LINE)
        b.set(Edge("H", 1, 0), LINE)           # edge going left from dot (1, 1)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("V", 1, 1): CROSS})


class TestTwoNextToAThree(unittest.TestCase):
    RULE_NAME = "Two Next to a Three"

    def run_on(self, text, crossed):
        b = board_from(text)
        for e in crossed:
            b.set(e, CROSS)
        return run_rule(RULE[self.RULE_NAME], b)

    def test_single_2(self):
        # like the screenshot: 2 at (0, 0) with its left crossed, 3 at (1, 1)
        result = self.run_on("2 . .\n. 3 .\n. . .", [Edge("V", 0, 0)])
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE,                          # the 2's top (other far side)
            Edge("H", 2, 1): LINE, Edge("V", 1, 2): LINE,   # the 3's bottom + right
        })

    def test_chain_of_2s(self):
        result = self.run_on("2 . . .\n. 2 . .\n. . 3 .\n. . . .", [Edge("V", 0, 0)])
        got = {c.edge: c.new_state for c in result.changes}
        self.assertEqual(got, {
            Edge("H", 0, 0): LINE,
            Edge("H", 3, 2): LINE, Edge("V", 2, 3): LINE,
        })

    def test_no_far_side_crossed_does_nothing(self):
        self.assertEqual(self.run_on("2 . .\n. 3 .\n. . .", []).changes, [])

    def test_flags_both_far_sides_crossed(self):
        result = self.run_on("2 . .\n. 3 .\n. . .", [Edge("V", 0, 0), Edge("H", 0, 0)])
        self.assertTrue(result.problems)


class TestSquareParity(unittest.TestCase):
    RULE_NAME = "Square Parity"

    # the 8 edges entering the corners of the middle square (1, 1) of a 3x3 board
    A, B = Edge("V", 0, 1), Edge("H", 1, 0)        # top-left dot: up, left
    C, D = Edge("V", 0, 2), Edge("H", 1, 2)        # top-right dot: up, right
    E, F = Edge("H", 2, 0), Edge("V", 2, 1)        # bottom-left dot: left, down
    G, H = Edge("H", 2, 2), Edge("V", 2, 2)        # bottom-right dot: right, down

    def run_on(self, lines, crossed, text=". . .\n. . .\n. . ."):
        b = board_from(text)
        for e in lines:
            b.set(e, LINE)
        for e in crossed:
            b.set(e, CROSS)
        return {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}

    def test_odd_fills_the_last_one(self):
        got = self.run_on([self.A], [self.B, self.C, self.D, self.E, self.F, self.G])
        self.assertEqual(got, {self.H: LINE})

    def test_even_crosses_the_last_one(self):
        got = self.run_on([self.A, self.D], [self.B, self.C, self.E, self.F, self.G])
        self.assertEqual(got, {self.H: CROSS})

    def test_line_turning_along_a_side_still_counts(self):
        # the counterexample: a line comes into the top-left dot and turns
        # along the square's top side -- it still counts as 1 line in
        got = self.run_on([self.A, Edge("H", 1, 1)],
                          [self.B, self.C, self.D, self.E, self.F, self.G, Edge("V", 1, 1)])
        self.assertEqual(got, {self.H: LINE})

    def test_two_undecided_does_nothing(self):
        self.assertEqual(self.run_on([self.A], [self.B, self.C, self.D, self.E, self.F]), {})

    def test_clue_square_works_too(self):
        got = self.run_on([self.A], [self.B, self.C, self.D, self.E, self.F, self.G],
                          text=". . .\n. 2 .\n. . .")
        self.assertEqual(got, {self.H: LINE})

    def test_border_square(self):
        # top-left square of a 2x2 board: only 4 entering edges exist
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 1), LINE)            # top-right dot: right
        b.set(Edge("V", 1, 0), CROSS)           # bottom-left dot: down
        b.set(Edge("H", 1, 1), CROSS)           # bottom-right dot: right
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got.get(Edge("V", 1, 1)), LINE)   # bottom-right dot: down

    def test_side_check_crosses_bottom(self):
        # like the screenshot: 3 lines enter (top-right from the right,
        # bottom-left from the left, bottom-right from the right); the two
        # edges going down from the bottom dots are undecided. Filling the
        # bottom side would fill up both bottom dots and cross both of those.
        got = self.run_on([self.D, self.E, self.G], [self.A, self.B, self.C])
        self.assertEqual(got, {Edge("H", 2, 1): CROSS})

    def test_side_check_needs_odd(self):
        # only 2 lines enter (even): no side is ruled out
        got = self.run_on([self.E, self.G], [self.A, self.B, self.C, self.D])
        self.assertEqual(got, {})


class TestNoSelfLoopLookAhead(unittest.TestCase):
    RULE_NAME = "No Self Loop (Look-Ahead)"

    def two_step_board(self):
        # a line over the top of the two top squares, down both sides:
        #   +───+───+
        #   │   x   │
        #   +   +   +      loose ends at dots (1, 0) and (1, 2) -- two edges apart
        #     2 x
        #   +   +   +
        b = board_from(". .\n2 .")
        for e in (Edge("H", 0, 0), Edge("H", 0, 1), Edge("V", 0, 0), Edge("V", 0, 2)):
            b.set(e, LINE)
        b.set(Edge("V", 0, 1), CROSS)          # the middle dot (1, 1) can only go
        b.set(Edge("V", 1, 1), CROSS)          # left or right
        return b

    def test_two_step_loop_is_crossed(self):
        b = self.two_step_board()
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        # filling either middle edge forces the other and closes the top loop,
        # which leaves the 2 with only 1 line -> both are crossed
        self.assertEqual(got, {Edge("H", 1, 0): CROSS, Edge("H", 1, 1): CROSS})

    def test_plain_rule_8_does_not_see_it(self):
        b = self.two_step_board()
        self.assertEqual(run_rule(RULE["No Self Loop"], b).changes, [])

    def test_does_not_change_the_real_board_while_trying(self):
        b = self.two_step_board()
        before = dict(b.state)
        run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(b.state, before)

    def test_is_marked_last_resort(self):
        self.assertTrue(RULE[self.RULE_NAME].last_resort)
        self.assertFalse(RULE["No Self Loop"].last_resort)


class TestAutoMode(unittest.TestCase):
    def test_auto_solves_the_5x5_and_matches_the_site(self):
        import main
        b = Board(decode_task("a32a33g03c2a3a213"))
        session = main.Session(b, "7caa4fc7044cce23eb01400151fa4bd2")
        session.speed_index = len(main.SPEEDS) - 1
        session.auto()
        self.assertTrue(verify.is_solved(b))
        self.assertTrue(verify.matches_hash(b, "7caa4fc7044cce23eb01400151fa4bd2"))

    def test_celebration_ends_in_a_box_with_no_emojis(self):
        import render
        frames = render.celebration_frames(["30 x 30", "matches the site's answer"])
        for lines, delay in frames:
            text = "\n".join(lines)
            # plain characters only (ANSI colour codes aside)
            self.assertTrue(all(ord(ch) < 128 for ch in text))
        last = "\n".join(frames[-1][0])
        self.assertIn("PUZZLE SOLVED!", last)
        self.assertIn("30 x 30", last)
        self.assertIn("matches the site's answer", last)
        self.assertIn("+" + "-" * (render.BOX_RIGHT - render.BOX_LEFT - 1) + "+", last)
        # fireworks 5 s, then falling glitter, then the box is held
        self.assertAlmostEqual(sum(d for _, d in frames[:render.FIREWORK_FRAMES]), 5.0)

    def test_win_details(self):
        import main
        b = Board(decode_task("a32a33g03c2a3a213"))
        session = main.Session(b, "7caa4fc7044cce23eb01400151fa4bd2")
        session.speed_index = len(main.SPEEDS) - 1
        session.auto()
        details = session.win_details()
        self.assertEqual(details[0], "5 x 5")
        self.assertEqual(details[1], "matches the site's answer")
        self.assertTrue(details[2].startswith("auto: "))

    def test_celebration_plays_once_when_solved(self):
        import main
        import render
        plays = []
        original = render.celebrate
        render.celebrate = lambda board, labels=True, details=(): plays.append(1)
        try:
            b = Board(decode_task("a32a33g03c2a3a213"))
            session = main.Session(b, None)
            session.speed_index = len(main.SPEEDS) - 1
            session.check_for_win()
            self.assertEqual(plays, [])                 # not solved yet
            session.auto()
            session.check_for_win()
            session.check_for_win()
            self.assertEqual(plays, [1])                # played once, not twice
            self.assertTrue(any("PUZZLE SOLVED" in m for m in session.messages))
            b.undo()                                    # un-solve it...
            session.check_for_win()
            session.auto()                              # ...and solve it again
            session.check_for_win()
            self.assertEqual(plays, [1, 1])             # plays again
        finally:
            render.celebrate = original

    def test_last_resort_only_runs_when_a_pass_changes_nothing(self):
        import main
        from rules.base import Rule
        calls = []
        normal_runs = []

        def last_resort_fn(board, result):
            calls.append(len(normal_runs))
        def normal_fn(board, result):
            normal_runs.append(1)
        test_rules = [Rule(1, "Normal", "", normal_fn), Rule(2, "Last", "", last_resort_fn, last_resort=True)]

        original = list(main.RULES)
        main.RULES[:] = test_rules
        try:
            session = main.Session(board_from(". .\n. ."), None)
            session.speed_index = len(main.SPEEDS) - 1
            session.auto()
        finally:
            main.RULES[:] = original
        # the normal rule ran one pass (no changes), then the last resort ran once
        self.assertEqual(normal_runs, [1])
        self.assertEqual(calls, [1])

    def test_last_resorts_run_one_at_a_time_cheapest_first(self):
        import main
        from rules.base import Rule
        order = []

        def normal_fn(board, result):
            order.append("normal")
        def cheap_fn(board, result):                  # makes progress the first time only
            order.append("cheap")
            result.cross(Edge("H", 0, 0), "test")
        def slow_fn(board, result):
            order.append("slow")
        test_rules = [Rule(1, "Normal", "", normal_fn),
                      Rule(2, "Cheap", "", cheap_fn, last_resort=True),
                      Rule(3, "Slow", "", slow_fn, last_resort=True)]

        original = list(main.RULES)
        main.RULES[:] = test_rules
        try:
            session = main.Session(board_from("."), None)
            session.speed_index = len(main.SPEEDS) - 1
            session.auto()
        finally:
            main.RULES[:] = original
        # pass 1: normal stuck -> cheap helps -> back to normal (slow skipped)
        # pass 2: normal stuck -> cheap stuck -> slow runs -> nothing -> stop
        self.assertEqual(order, ["normal", "cheap", "normal", "cheap", "slow"])


class TestOneNextToAThree(unittest.TestCase):
    RULE_NAME = "One Next to a Three"

    def changes(self, text, crossed=()):
        b = board_from(text)
        for e in crossed:
            b.set(e, CROSS)
        result = run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(result.problems, [])
        return {c.edge: c.new_state for c in result.changes}

    def test_on_top_border(self):
        got = self.changes(". 3 1 .\n. . . .")     # 3 at (0,1), 1 at (0,2), both on the top border
        self.assertEqual(got, {
            Edge("H", 0, 1): LINE,                     # the 3's top
            Edge("H", 1, 2): CROSS,                    # the 1's bottom
            Edge("V", 0, 3): CROSS,                    # the 1's right
        })

    def test_with_a_crossed_edge(self):
        got = self.changes(". . . .\n. 3 1 .\n. . . .", crossed=[Edge("V", 0, 2)])  # edge above dot (1, 2)
        self.assertEqual(got, {Edge("H", 1, 1): LINE, Edge("H", 2, 2): CROSS, Edge("V", 1, 3): CROSS})

    def test_stacked_on_left_border(self):
        got = self.changes("1 .\n3 .\n. .")         # 1 at (0,0) above the 3 at (1,0)
        self.assertEqual(got, {
            Edge("V", 1, 0): LINE,                     # the 3's left
            Edge("H", 0, 0): CROSS,                    # the 1's top
            Edge("V", 0, 1): CROSS,                    # the 1's right
        })

    def test_open_ends_do_nothing(self):
        self.assertEqual(self.changes(". . . .\n. 3 1 .\n. . . ."), {})


class TestTwoThenThree(unittest.TestCase):
    RULE_NAME = "Two Then Three"

    def changes(self, text, crossed):
        b = board_from(text)
        for e in crossed:
            b.set(e, CROSS)
        return {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}

    def test_three_on_the_right(self):
        got = self.changes(". 2 3 .", [Edge("V", 0, 1)])      # the 2's left crossed
        self.assertEqual(got, {Edge("V", 0, 3): LINE})        # the 3's right

    def test_three_above(self):
        got = self.changes(". 3 .\n. 2 .\n. . .", [Edge("H", 2, 1)])   # the 2's bottom crossed
        self.assertEqual(got, {Edge("H", 0, 1): LINE})                 # the 3's top

    def test_crossed_side_not_opposite_does_nothing(self):
        got = self.changes(". . .\n. 2 3\n. . .", [Edge("H", 1, 1)])   # the 2's top crossed, 3 on the right
        self.assertEqual(got, {})


class TestRegionParity(unittest.TestCase):
    RULE_NAME = "Region Parity"

    def board_with_two_rooms(self, bottom_middle):
        """1 row of 3 squares. Every edge is decided except two little loops
        of undecided edges (left square, right square), joined only by the
        top-middle edge H(0,1) -- the one way between the two regions.
        The bottom-middle edge H(1,1) is set to `bottom_middle`."""
        b = board_from(". . .")
        undecided = {Edge("H", 0, 0), Edge("V", 0, 0), Edge("V", 0, 1), Edge("H", 1, 0),   # left square
                     Edge("H", 0, 2), Edge("V", 0, 3), Edge("V", 0, 2), Edge("H", 1, 2),   # right square
                     Edge("H", 0, 1)}                                                      # the link
        for e in b.all_edges():
            if e not in undecided:
                b.set(e, CROSS)
        b.set(Edge("H", 1, 1), bottom_middle)
        return b

    def test_odd_loose_ends_fill_the_link(self):
        b = self.board_with_two_rooms(LINE)      # 1 loose end in each region
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 0, 1): LINE})

    def test_even_loose_ends_cross_the_link(self):
        b = self.board_with_two_rooms(CROSS)     # no loose ends
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {Edge("H", 0, 1): CROSS})

    def test_no_single_link_does_nothing(self):
        b = board_from(". .\n. .")               # everything undecided: no edge is the only link
        self.assertEqual(run_rule(RULE[self.RULE_NAME], b).changes, [])

    def test_is_last_resort(self):
        self.assertTrue(RULE[self.RULE_NAME].last_resort)


class TestLocalTry(unittest.TestCase):
    RULE_NAME = "Local Try"

    def test_filling_breaks_a_clue(self):
        b = board_from("1 .\n. .")
        b.set(Edge("H", 0, 0), LINE)           # the 1 already has its line
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got.get(Edge("V", 0, 0)), CROSS)   # filling its left would make 2

    def test_two_steps_away(self):
        # a line arrives at dot (0, 1) on the top border; it can go right, or
        # down to dot (1, 1) -- where every other edge is crossed out.
        b = board_from(". . .\n. . .")
        b.set(Edge("H", 0, 0), LINE)
        for e in (Edge("H", 1, 0), Edge("H", 1, 1), Edge("V", 1, 1)):
            b.set(e, CROSS)
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got.get(Edge("V", 0, 1)), CROSS)   # going down ends in a dead end
        self.assertEqual(got.get(Edge("H", 0, 1)), LINE)    # crossing right forces going down

    def test_does_not_change_the_real_board_while_trying(self):
        b = board_from("1 .\n. .")
        b.set(Edge("H", 0, 0), LINE)
        before = dict(b.state)
        run_rule(RULE[self.RULE_NAME], b)
        self.assertEqual(b.state, before)

    def test_is_last_resort(self):
        self.assertTrue(RULE[self.RULE_NAME].last_resort)

    def test_small_loop_counts_as_breaking(self):
        # two 3s side by side with a 1 elsewhere: if their shared side were
        # crossed, the 3s would need every other side -- a closed loop round
        # both squares that leaves the 1 out. So the shared side is filled.
        b = board_from(". . . .\n. 3 3 .\n. . . .\n. . . 1")
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got.get(Edge("V", 1, 2)), LINE)

    def test_runs_the_normal_rules_inside_a_try(self):
        # a stand-in normal rule that objects whenever edge H(0,0) is a line:
        # only by running it inside the try can Local Try learn H(0,0) is crossed
        from rules.base import RULES, Rule
        watched = Edge("H", 0, 0)

        def objects_to_watched_line(board, result):
            if board.get(watched) == LINE:
                result.flag("test rule objects")
        test_rule = Rule(98, "Test Objector", "test", objects_to_watched_line)
        RULES.append(test_rule)
        try:
            b = board_from(". . .\n. . .\n. . .")
            got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        finally:
            RULES.remove(test_rule)
        self.assertEqual(got.get(watched), CROSS)


class TestThreeWithTwoOnes(unittest.TestCase):
    RULE_NAME = "Three With Two Ones"

    def test_one_left_and_one_below(self):
        # the spot from the monthly: a 1 left of the 3 and a 1 below it
        b = board_from(". . .\n. 1 3\n. . 1")
        got = {c.edge: c.new_state for c in run_rule(RULE[self.RULE_NAME], b).changes}
        self.assertEqual(got, {
            Edge("H", 1, 1): CROSS, Edge("V", 1, 1): CROSS,   # left 1: top + left
            Edge("H", 3, 2): CROSS, Edge("V", 2, 3): CROSS,   # lower 1: bottom + right
        })

    def test_ones_on_opposite_sides_do_nothing(self):
        b = board_from(". . .\n1 3 1\n. . .")
        self.assertEqual(run_rule(RULE[self.RULE_NAME], b).changes, [])


class TestFollowUpCheck(unittest.TestCase):
    def test_new_line_joining_an_old_one_crosses_the_rest(self):
        import main
        b = board_from(". .\n. .")
        b.set(Edge("H", 0, 0), LINE)           # line along the top, ends at corner dot (0, 0)
        b.set(Edge("V", 1, 0), LINE)           # a separate line on the left, below dot (1, 0)
        session = main.Session(b, None)
        session.speed_index = len(main.SPEEDS) - 1     # instant: no animation
        session.run(RULE["Continue Line"])     # fills V(0,0), joining the two lines at dot (1, 0)
        self.assertEqual(b.get(Edge("V", 0, 0)), LINE)
        self.assertEqual(b.get(Edge("H", 1, 0)), CROSS)  # follow-up: dot (1, 0) is now full
        # the follow-up happened straight after the line it belongs to, before
        # the rule's next change (Continue Line also fills H(2,0) later on)
        order = [edge for edge, _ in b.history[-1]]
        self.assertEqual(order[:2], [Edge("V", 0, 0), Edge("H", 1, 0)])
        self.assertIn(Edge("H", 2, 0), order[2:])

        b.undo()                               # one undo reverses the rule AND its follow-up
        self.assertEqual(b.get(Edge("V", 0, 0)), EMPTY)
        self.assertEqual(b.get(Edge("H", 1, 0)), EMPTY)

    def test_crossing_an_edge_starts_a_follow_up_too(self):
        import main
        from rules.base import Rule
        b = board_from(". .")                  # 1 row, 2 squares
        b.set(Edge("H", 0, 0), LINE)           # a line ending at the top-middle dot (0, 1)

        def cross_one(board, result):
            result.cross(Edge("V", 0, 1), "test")   # cross the middle wall
        session = main.Session(b, None)
        session.speed_index = len(main.SPEEDS) - 1
        session.run(Rule(99, "Test Rule", "test", cross_one))

        # the line at dot (0, 1) now has only one way on: to the right
        self.assertEqual(b.get(Edge("H", 0, 1)), LINE)

    def test_follow_up_keeps_going_as_far_as_forced(self):
        import main
        from rules.base import Rule
        b = board_from(". . .")                # 1 row, 3 squares
        b.set(Edge("V", 0, 1), CROSS)          # inside walls crossed: the loop has to
        b.set(Edge("V", 0, 2), CROSS)          # go all the way round the outside

        def fill_one(board, result):
            result.fill(Edge("H", 0, 0), "test")
        session = main.Session(b, None)
        session.speed_index = len(main.SPEEDS) - 1
        session.run(Rule(99, "Test Rule", "test", fill_one))

        outside = [Edge("H", 0, 0), Edge("H", 0, 1), Edge("H", 0, 2), Edge("V", 0, 3),
                   Edge("H", 1, 2), Edge("H", 1, 1), Edge("H", 1, 0), Edge("V", 0, 0)]
        self.assertEqual([b.get(e) for e in outside], [LINE] * 8)   # one fill drew the whole loop

    def test_rule_change_blocked_by_earlier_follow_up_is_flagged(self):
        import main
        from rules.base import Rule
        b = board_from(". .\n. .")
        b.set(Edge("H", 1, 0), LINE)           # existing line ending at dot (1, 1)

        def fill_two_from_one_dot(board, result):
            result.fill(Edge("H", 1, 1), "test")     # completes dot (1, 1) -> follow-up crosses V(0,1), V(1,1)
            result.fill(Edge("V", 1, 1), "test")     # ...so this one is now blocked
        test_rule = Rule(99, "Test Rule", "test", fill_two_from_one_dot)

        session = main.Session(b, None)
        session.speed_index = len(main.SPEEDS) - 1
        changes, problems = session.run(test_rule)
        self.assertEqual(b.get(Edge("V", 1, 1)), CROSS)  # not overwritten
        self.assertEqual(problems, 1)


class TestBoardAndVerify(unittest.TestCase):
    def test_undo(self):
        b = board_from("0")
        result = run_rule(RULE["Clue Check"], b)
        b.apply(result.changes)
        self.assertTrue(b.is_full())
        b.undo()
        self.assertTrue(all(s == EMPTY for s in b.state.values()))

    def test_single_square_loop_and_hash(self):
        b = Board(decode_task("a"))       # 1x1, no clue
        for e in b.all_edges():
            b.set(e, LINE)
        self.assertTrue(verify.is_solved(b))
        self.assertEqual(b.serialize(), "yyyy")


if __name__ == "__main__":
    unittest.main()
