# Slitherlink step-by-step solver

Offline, rule-by-rule solver for puzzles from puzzle-loop.com. You pick a
named rule, it sweeps the whole board, and you watch each change appear.

## Download

You need Python 3.8 or newer; nothing else to install (it only uses Python's
standard library).

```bash
git clone https://github.com/lcforbes4/SlitherLinkSolver.git
cd SlitherLinkSolver
```

Run it in a real terminal (macOS Terminal, iTerm, a Linux terminal, or
Windows Terminal), since it waits for you to type commands.

## Run it

Try the small 5x5 test puzzle first (press `a` to watch auto solve it):

```bash
python3 main.py a32a33g03c2a3a213 --hash 7caa4fc7044cce23eb01400151fa4bd2
```

- The **task string** is in the puzzle page's code: open the browser console
  (Cmd+Option+J) on the puzzle page and type `task`.
- `--hash` (optional) is the page's `hashedSolution` value (view source,
  search for `hashedSolution`). With it, a finished board is checked against
  the site's real answer.
- Non-square puzzles (25x30) need `--w` and `--h`.
- `--grid file.txt` loads a hand-typed puzzle instead (one row per line,
  `.` for no clue, e.g. `. 3 2 . 3`).

Menu: a rule's number runs that rule · `a` auto (all rules until nothing changes)
· `u` undo · `l` list last changes with reasons · `s` animation speed
· `c` row/column labels on/off · `q` quit.

Rules marked `*` are **last resort**: auto runs the other rules pass after
pass, and only tries a last-resort rule when a whole pass changes nothing.
The last-resort rules are tried one at a time in number order (cheapest
first, so Local Try, the slowest, goes last); as soon as one makes progress,
auto goes back to the normal rules. You can still run
one yourself by its number at any time. To mark a rule, add
`last_resort=True` to its `@rule(...)` line.

The `r1 r2 …` / `c1 c2 …` around the board are row and column labels, not
clues. Start with `--no-labels` to hide them, or press `c` at any time.

**When you solve it:** a full-screen celebration plays (about 7.5 seconds):
fireworks for 5 seconds, then the glitter falls and stacks into a box
saying PUZZLE SOLVED!, with the puzzle size, whether it matches the site's
answer (if you gave `--hash`), and auto's passes and time. Then the board
comes back with a "PUZZLE SOLVED!" banner above the menu. After auto, only a
one-line summary is shown (plus any ⚠ problems), not every rule's changes. (If you
undo and solve it again, it plays again.)

**Follow-up check:** the moment a rule fills or crosses out an edge, its two
end dots are settled, and it keeps going as far as it's forced before the rule's next
change:
- a dot with 2 lines gets its other edges crossed out (Full Dot)
- a dot with 1 line and only one way out gets that way filled (Continue Line)

Every edge the follow-up changes has its dots checked too, so a line keeps
extending until it reaches a dot with a real choice. It's all part of the
same step (one `u` undoes it) and its changes show as "(follow-up)" in the
`l` list. If a later change from the same rule lands on an edge a follow-up
already set the other way, it's flagged with ⚠ instead of being overwritten.

Rules never change the board silently. If one finds something impossible, it
prints a ⚠ line saying where. That means the rule (or an earlier step) needs
looking at.

## How the files fit together

```
                 you paste:  task string  [+ --hash]
                                  │
                                  ▼
                        ┌──────────────────┐
                        │     main.py      │  menu, animation, undo, auto
                        └──┬─────┬─────┬───┘
            decode string  │     │     │  run the chosen rule
                           ▼     │     ▼
              ┌─────────────┐    │   ┌──────────────────────────┐
              │ puzzle.py   │    │   │ rules/                   │
              │ string →    │    │   │  base.py   tools + menu  │
              │ clue grid   │    │   │  clue_rules.py    (1)    │
              └──────┬──────┘    │   │  line_rules.py    (2)    │
                     ▼           │   │  pattern_rules.py (3)    │
              ┌─────────────┐    │   └────────────┬─────────────┘
              │  board.py   │◄───┼────────────────┘ returns Changes
              │ every edge: │    │                  (edge, new state, why)
              │ EMPTY/CROSS/│    │
              │ LINE + undo │    │
              └──────┬──────┘    │
                     ▼           ▼
              ┌──────────────────────┐        ┌──────────────┐
              │      render.py       │        │  verify.py   │
              │ draws board, colours │        │ one loop?    │
              │ just-changed edges   │        │ md5 == hash? │
              └──────────────────────┘        └──────────────┘
```

## Rules

| # | Name | What it does |
|---|------|--------------|
| 1 | Clue Check | Clue satisfied → cross out its remaining sides. Not satisfied but lines + open sides = clue → fill the open sides. |
| 2 | Continue Line | A dot with 1 line and exactly 1 open edge → fill that edge. |
| 3 | Adjacent Threes | Two 3s sharing a side → fill the shared edge and both far sides, cross out the edges that continue the shared edge past the pair. |
| 4 | Three in a Corner | A 3's corner dot has no way out (its outside edges are crossed or off the grid) → fill the 3's two sides at that corner. |
| 5 | Diagonal Threes | 2+ 3s in an unbroken diagonal line → fill the outer corner (2 sides) of each end 3, and cross out the other edges at those outer corner dots. Also works for two 3s with only 2s between them on the diagonal (3, 2, 3 / 3, 2, 2, 3 …); mixed lines like 3, 2, 3, 2, 3 aren't treated as one. |
| 6 | Line Into a 3 | A line enters a 3's corner from outside → cross out the other outside edge at that dot (no turning away) and fill the 3's two far sides. Also works when the line enters the outer corner of a diagonal chain of 2s that leads to the 3. |
| 7 | Full Dot | A dot already has 2 lines (a corner or straight through) → cross out its other edges. |
| 8 | No Self Loop | The two loose ends of one piece of line are neighbours → cross the edge between them (it would close a small loop), unless closing it would be the whole answer. |
| 9 | No Dead Ends | A dot with no lines and every edge but one crossed out (off-grid edges count as crossed) → cross out the last edge too. |
| 10 | Two in a Corner | A 2 with a dead corner (outside edges crossed or off the grid) and one far side crossed → fill its two sides at that corner, cross the other two. Also: at the 2's opposite corner the two outside edges match: one crossed (or off the grid) → cross the other, one filled → fill the other (works along a diagonal chain of 2s too). Also: exactly one line leaves each of the 2's other two corners, so the Line Into results apply to the squares diagonally past them, and the two outside edges at such a corner are opposites (one filled → cross the other, one crossed or off the grid → fill the other); any 2s diagonally past those corners also get their far-corner outside edges treated as opposites. All of this also applies to every 2 in the diagonal chain going away from the dead corner. |
| 11 | Diagonal Lines Into a 2 | Lines come in from outside at both outer corners of a 2, or of an unbroken diagonal chain of 2s → cross out the other outside edge at each of those corners (the lines can't turn away). |
| 12 | One in a Corner | A 1 with a dead corner (grid corner, or every outside edge at that dot crossed) → cross out the 1's two sides at that corner. |
| 13 | Line Into a 1 | A line enters a 1's corner from outside and can't turn away (other outside edges crossed or off the grid) → cross out the 1's two far sides. Also works when the line enters the outer corner of a diagonal chain of 2s that leads to the 1. |
| 14 | Line Into a 2 | A line enters a 2's corner from outside and one of the 2's far sides is crossed → cross out the turn-away edge at that corner and fill the other far side. Also works when the line enters the outer corner of a diagonal chain of 2s that leads to that 2. Also: if the line entering a 2 can't turn away, the two outside edges at the 2's far corner are opposites (one filled → cross the other, one crossed or off the grid → fill the other), for every 2 down a chain too. In that same case the 2's two far sides are opposites too: one filled → cross the other. |
| 15 | Next to 2s in a Corner | A 2 with a dead corner, then (optionally) a diagonal chain of 2s going away from it. Ends at a 1 → cross the 1's two sides at the shared corner. Ends at a 3 → every 2 gets its sides at the dead-corner side filled and the rest crossed, and the 3's two sides at the shared corner are filled. |
| 16 | One's Crossed Corner | A 1 with both sides at one corner crossed → exactly one line comes out of its opposite corner, so walk diagonally past it (through any 2s): a 2 with a far side crossed gets its other far side filled; a 1 at the end gets its far sides crossed; a 3 at the end gets its far sides filled. Also, whatever is diagonally past: the two edges at the 1's opposite corner closest to the 1 are opposites (one filled → cross the other, one crossed or off the grid → fill the other). |
| 17 | Three's Filled Corner | A 3 with both sides at one corner filled → exactly one line leaves its opposite corner. Walk diagonally past it (through any 2s): each 2's two outside edges at its far corner are opposites (one filled → cross the other, one crossed or off the grid → fill the other); a 1 at the end gets its far sides crossed. Also: the two outside edges at the 3's own opposite corner are opposites (one crossed or off the grid → fill the other, one filled → cross the other). |
| 18 | Two Next to a Three | A 2 diagonal from a 3 (or a diagonal chain of 2s going away from it), with one of a 2's far sides crossed → fill that 2's other far side and the 3's far corner. |
| 19 | Square Parity | A square (any square, clue or not) with exactly one undecided edge entering its corners (from outside) → count the filled entering edges (including ones that turn along its sides): odd → fill it, even → cross it. Side check: when the count is odd, an undecided side of the square that, if filled, would fill up its end dots and cross every remaining undecided entering edge is crossed out. |
| 20* | No Self Loop (Look-Ahead) | **Last resort.** For a piece of line whose loose ends are close (same square, or two squares side by side): try each undecided edge at a loose end on a scratch copy, follow up as far as forced; if that closes a small loop, cross the edge out. Extends rule 8 a few forced steps out. |
| 21 | One Next to a Three | A 1 and a 3 share a side, and at one end of it the dot's outward edge is crossed or off the grid → fill the 3's side at that dot and cross out the 1's two sides at its corner opposite that dot. |
| 22 | Two Then Three | A 2 with one side crossed, and a 3 sharing the 2's opposite side → fill the 3's far side. |
| 23* | Region Parity | **Last resort.** A closed-off region (a group of dots whose only undecided way out is one edge) → count the loose ends inside: odd → fill that edge, even → cross it. |
| 24* | Local Try | **Last resort.** For each undecided edge, on a scratch copy: fill it, then within 3 squares apply the simple rules after every change and all the normal rules (repeating while they find things); if that breaks something — including closing a small loop — cross it out. Otherwise try it crossed out; if that breaks something, fill it. |
| 25 | Three With Two Ones | A 3 with a 1 on two of its sides that meet at a corner → cross out each 1's two sides that don't touch that corner. |

## Adding a rule

1. Write `def my_rule(board, result):` in a file in `rules/`. Use
   `result.fill(edge, reason)`, `result.cross(edge, reason)` and
   `result.flag(message)`.
2. Put `@rule(4, "My Rule", "one-line description")` above it.
3. If it's a new file, import it in `rules/__init__.py`.

Useful board helpers: `board.squares()`, `board.dots()`, `board.clue(r, c)`,
`board.square_edges(r, c)`, `board.dot_edges(r, c)`, `board.count(edges, LINE)`,
`board.with_state(edges, EMPTY)`. Edge naming is explained at the top of `board.py`.

## Tests

```bash
python3 -m unittest discover tests
```

## License

MIT (see `LICENSE`).
