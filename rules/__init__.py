"""
rules/ -- every named solving rule lives in this folder.

To add a rule:
  1. write a function  def my_rule(board, result): ...  in one of the files
     (or a new file), using result.fill / result.cross / result.flag
  2. put  @rule(number, "Name", "one-line description")  above it
  3. if it's a new file, import it below

It then shows up in the menu automatically.
"""

from rules.base import RULES, Rule, RuleResult, rule, run_rule

# Importing these files registers their rules.
from rules import clue_rules      # 1 Clue Check
from rules import line_rules      # 2 Continue Line, 7 Full Dot, 9 No Dead Ends
from rules import pattern_rules   # 3-6, 10-18, 21-22: patterns of clues, corners and diagonals
from rules import loop_rules      # 8 No Self Loop, 20 No Self Loop (Look-Ahead)
from rules import parity_rules    # 19 Square Parity, 23 Region Parity
from rules import try_rules       # 24 Local Try

__all__ = ["RULES", "Rule", "RuleResult", "rule", "run_rule"]
