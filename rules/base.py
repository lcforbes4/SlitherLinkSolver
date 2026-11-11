"""
rules/base.py -- the tools every rule uses.

A rule is a function   my_rule(board, result)   that LOOKS at the board and
writes what it wants into `result` using:

    result.fill(edge, reason)    -> this edge must be a LINE
    result.cross(edge, reason)   -> this edge must be crossed out
    result.flag(message)         -> something impossible was found

Rules never change the board themselves. main.py applies the changes
afterwards (animated, and undoable as one step).

fill/cross automatically:
  * skip edges that are already in the wanted state (no fake "changes")
  * flag a contradiction if the edge is already the opposite state, or if
    the same sweep asked for both LINE and CROSS on one edge
"""

from dataclasses import dataclass, field
from typing import Callable

from board import CROSS, EMPTY, LINE, Change, Problem, describe_edge


@dataclass
class Rule:
    number: int
    name: str
    description: str
    function: Callable
    last_resort: bool = False   # auto mode only runs it when nothing else works


RULES = []   # filled in by the @rule decorator, sorted by number


def rule(number, name, description, last_resort=False):
    """Decorator that adds a function to the rule menu.
    last_resort=True: auto mode only runs it when a whole pass of the other
    rules changes nothing (it can still be run by number at any time)."""
    def register(function):
        RULES.append(Rule(number, name, description, function, last_resort))
        RULES.sort(key=lambda r: r.number)
        return function
    return register


class RuleResult:
    def __init__(self, board, rule_name):
        self.board = board
        self.rule_name = rule_name
        self.changes = []
        self.problems = []
        self._planned = {}   # edge -> state already asked for in this sweep

    def fill(self, edge, reason):
        self._want(edge, LINE, reason)

    def cross(self, edge, reason):
        self._want(edge, CROSS, reason)

    def flag(self, message):
        self.problems.append(Problem(self.rule_name, message))

    def _want(self, edge, state, reason):
        current = self.board.get(edge)
        if current == state:
            return                                   # already done
        if current != EMPTY:
            self.flag(f"wants {describe_edge(edge)} to be {state.value}, "
                      f"but it is already {current.value}  ({reason})")
            return
        planned = self._planned.get(edge)
        if planned == state:
            return                                   # already asked for
        if planned is not None:
            self.flag(f"asked for {describe_edge(edge)} to be both "
                      f"{planned.value} and {state.value}  ({reason})")
            return
        self._planned[edge] = state
        self.changes.append(Change(edge, state, self.rule_name, reason))


def run_rule(rule_obj, board):
    """Run one rule over the whole board and return its RuleResult."""
    result = RuleResult(board, rule_obj.name)
    rule_obj.function(board, result)
    return result
