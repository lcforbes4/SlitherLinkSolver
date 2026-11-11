"""
main.py -- run the solver interactively.

    python3 main.py TASK_STRING [--hash FINGERPRINT] [--w W --h H]
    python3 main.py --grid my_puzzle.txt

Then pick a rule by number and watch it sweep the board.
"""

import argparse
import sys
import time

import render
import verify
from board import CROSS, EMPTY, LINE, Board, Problem, describe_edge
from puzzle import decode_task, parse_grid_text
from rules import RULES, run_rule
from rules.line_rules import forced_follow_up

SPEEDS = [("normal", 0.08), ("slow", 0.3), ("fast", 0.02), ("instant", 0.0)]


class Session:
    def __init__(self, board, expected_hash, labels=True):
        self.board = board
        self.expected_hash = expected_hash
        self.labels = labels          # show r1/c1 labels around the board?
        self.speed_index = 0
        self.last_changes = []
        self.messages = ["Blank puzzle loaded. Pick a rule to run."]
        self.celebrated = False       # has the "solved" celebration played yet?
        self.auto_stats = None        # (passes, seconds) if the last command was auto

    # ---------- screen ----------

    def menu_lines(self):
        lines = [""]
        lines.extend(self.messages)
        lines.append(verify.status_line(self.board, self.expected_hash))
        lines.append("")
        # rules in two columns: first half on the left, second half on the right
        half = (len(RULES) + 1) // 2
        name_width = max(len(r.name) for r in RULES)
        def entry(r):
            star = "*" if r.last_resort else " "       # * = last resort
            return f"{r.number:>2}{star} {r.name}"
        for left, right in zip(RULES[:half], RULES[half:] + [None]):
            line = f"  {entry(left):<{name_width + 4}}"
            if right:
                line += f"    {entry(right)}"
            lines.append(line)
        speed_name = SPEEDS[self.speed_index][0]
        labels_name = "on" if self.labels else "off"
        if any(r.last_resort for r in RULES):
            lines.append("   * last resort: auto only runs it when the other rules change nothing")
        lines.append("")
        lines.append(f"   a  auto  (run all rules until nothing changes)     "
                     f"u undo   l list last changes   s speed ({speed_name})   "
                     f"c labels ({labels_name})   q quit")
        return lines

    def redraw(self):
        recent = [c.edge for c in self.last_changes]
        render.show(self.board, recent=recent, status_lines=self.menu_lines(), labels=self.labels)

    # ---------- running rules ----------

    def apply_one(self, label, change, done):
        """Apply one change to the board and animate it.
        `done` collects every edge changed so far in this step."""
        self.board.apply_change(change)
        done.append(change.edge)
        delay = SPEEDS[self.speed_index][1]
        if delay > 0:
            render.show(self.board, recent=done, latest=change.edge, status_lines=[
                "", f"{label}: {change.reason}"], labels=self.labels)
            time.sleep(delay)

    def follow_up(self, edge, label, done):
        """After an edge is filled or crossed out, settle the dots it touches,
        and keep going as far as it's forced:

          * a dot with 2 lines        -> cross out its other edges  (Full Dot)
          * a dot with 1 line and only
            one way out               -> fill that way out          (Continue Line)

        Every change made here is applied (and animated) straight away, and
        the dots it touches are checked next -- so a line keeps extending
        until it reaches a dot with a real choice.
        Returns (changes made, problems found)."""
        return forced_follow_up(self.board, [edge], label,
                                apply=lambda change: self.apply_one(label, change, done))

    def run(self, rule_obj):
        """Sweep one rule over the board and apply its changes one at a time.
        Right after each edge is drawn (filled or crossed), follow it up (see follow_up)
        before moving on to the rule's next change.
        Returns (number of changes, number of problems)."""
        result = run_rule(rule_obj, self.board)
        follow_name = f"{rule_obj.name} (follow-up)"

        self.board.start_step()           # the sweep + its follow-ups = one undo
        done = []
        applied, follow_ups, problems = [], [], list(result.problems)

        for change in result.changes:
            # a follow-up earlier in this step may already have set this edge
            current = self.board.get(change.edge)
            if current == change.new_state:
                continue
            if current != EMPTY:
                problems.append(Problem(rule_obj.name,
                    f"wants {describe_edge(change.edge)} to be {change.new_state.value}, but a "
                    f"follow-up already made it {current.value}  ({change.reason})"))
                continue

            self.apply_one(rule_obj.name, change, done)
            applied.append(change)

            # follow-up, straight away, as far as it goes (after a fill or a cross)
            changes, found = self.follow_up(change.edge, follow_name, done)
            follow_ups.extend(changes)
            problems.extend(found)

        all_changes = applied + follow_ups
        self.last_changes = all_changes
        filled = sum(1 for c in all_changes if c.new_state == LINE)
        crossed = sum(1 for c in all_changes if c.new_state == CROSS)
        if all_changes:
            n = len(all_changes)
            extra = f", {len(follow_ups)} from follow-ups" if follow_ups else ""
            msg = (f"{rule_obj.name}: {n} change{'s' if n != 1 else ''} "
                   f"({filled} filled, {crossed} crossed out{extra})")
        else:
            msg = f"{rule_obj.name}: no changes"
        self.messages.append(msg)
        for problem in problems:
            self.messages.append(f"⚠ {problem.rule}: {problem.message}  -> this rule may need adjusting")
        return len(all_changes), len(problems)

    def auto(self):
        """Run the normal rules in order, over and over. When a whole pass
        changes nothing, try the last-resort rules ONE AT A TIME, in number
        order (cheapest first -- Local Try, the slowest, is numbered last).
        As soon as one changes something, go back to the normal rules. If
        none of them help, stop."""
        self.messages = []
        normal = [r for r in RULES if not r.last_resort]
        last_resorts = [r for r in RULES if r.last_resort]
        # each attempt in a pass: all the normal rules together, then each
        # last-resort rule on its own
        attempts = [normal] + [[r] for r in last_resorts]
        passes = 0
        started = time.time()
        while not verify.is_solved(self.board):
            passes += 1
            for attempt in attempts:
                changed = 0
                for rule_obj in attempt:
                    changes, problems = self.run(rule_obj)
                    changed += changes
                    if problems:
                        self.messages.append("Auto stopped because a problem was flagged.")
                        return
                if changed:
                    break                          # progress: start a new pass
            else:
                break                              # nothing helped
        # no long list of every rule's changes: just one summary line
        # (plus any ⚠ problems). If it's solved, the celebration takes over.
        problems = [m for m in self.messages if m.startswith("⚠")]
        self.messages = problems + [f"Auto finished after {passes} passes."]
        self.auto_stats = (passes, time.time() - started)

    # ---------- main loop ----------

    def check_for_win(self):
        """Play the celebration the first time the puzzle becomes solved, and
        keep the banner showing above the menu. If an undo un-solves it, it
        can play again later."""
        solved = verify.is_solved(self.board)
        if solved and not self.celebrated:
            self.celebrated = True
            render.celebrate(self.board, labels=self.labels, details=self.win_details())
        elif not solved:
            self.celebrated = False
        banner = render.celebration_lines()
        if solved and banner[1] not in self.messages:
            self.messages = banner + self.messages

    def win_details(self):
        """The short lines shown in the celebration box under PUZZLE SOLVED!
            30 x 30
            matches the site's answer
            auto: 42 passes, 46.0 s"""
        details = [f"{self.board.width} x {self.board.height}"]
        if self.expected_hash:
            matched = verify.matches_hash(self.board, self.expected_hash)
            details.append("matches the site's answer" if matched
                           else "does NOT match the site's answer")
        if self.auto_stats:
            passes, seconds = self.auto_stats
            details.append(f"auto: {passes} passes, {seconds:.1f} s")
        return details

    def loop(self):
        while True:
            self.check_for_win()
            self.redraw()
            try:
                command = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            self.auto_stats = None        # only "a" sets it again

            if command in ("q", "quit", "exit"):
                return
            elif command == "u":
                self.last_changes = []
                self.messages = ["Undid the last step." if self.board.undo() else "Nothing to undo."]
            elif command == "s":
                self.speed_index = (self.speed_index + 1) % len(SPEEDS)
                self.messages = [f"Animation speed: {SPEEDS[self.speed_index][0]}"]
            elif command == "c":
                self.labels = not self.labels
                self.messages = [f"Row/column labels {'on' if self.labels else 'off'}."]
            elif command == "l":
                if not self.last_changes:
                    self.messages = ["The last step made no changes."]
                else:
                    self.messages = ["Last changes:"] + [
                        f"  {'fill ' if c.new_state == LINE else 'cross'}  {describe_edge(c.edge)}  -- {c.reason}"
                        for c in self.last_changes
                    ]
            elif command == "a":
                self.auto()
            elif command.isdigit() and any(r.number == int(command) for r in RULES):
                self.messages = []
                self.run(next(r for r in RULES if r.number == int(command)))
            else:
                self.messages = [f"Unknown command {command!r}."]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Step-by-step Slitherlink solver")
    parser.add_argument("task", nargs="?", help="task string copied from puzzle-loop.com")
    parser.add_argument("--hash", help="the site's hashedSolution, to check the answer")
    parser.add_argument("--w", type=int, help="width in squares (only needed for non-square grids)")
    parser.add_argument("--h", type=int, help="height in squares (only needed for non-square grids)")
    parser.add_argument("--grid", help="text file with a hand-typed puzzle instead of a task string")
    parser.add_argument("--no-labels", action="store_true",
                        help="hide the r1/c1 row and column labels (press c in the menu to toggle)")
    args = parser.parse_args(argv)

    try:
        if args.grid:
            with open(args.grid) as f:
                puzzle = parse_grid_text(f.read())
        elif args.task:
            puzzle = decode_task(args.task, args.w, args.h)
        else:
            parser.error("give a task string or --grid FILE")
    except ValueError as err:
        sys.exit(f"Could not read the puzzle: {err}")

    Session(Board(puzzle), args.hash, labels=not args.no_labels).loop()


if __name__ == "__main__":
    main()
