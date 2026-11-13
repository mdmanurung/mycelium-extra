# Vocabulary for analysis structure

Adapted from Matt Pocock's codebase-design skill (MIT). The words keep their meaning. The examples are analyses. Use these terms and no others: not "component", "service", "API" or "boundary".

## Terms

**Module.** A script, a function or a step: anything with an interface and an implementation. `code/02_fit.R` is a module. So is a helper called from it.

**Interface.** Everything a caller must know to use the module correctly. For a step this is: the files it reads and where they must be, the files it writes, its parameters and knobs, its invariants (donor IDs match the matrix columns), its seeds, and the order it must run in. A script that needs you to run `01_` first and set an environment variable has that in its interface, even if no header says so.

**Implementation.** What sits inside: the code that does the work.

**Depth.** The analysis done per unit of interface. A step is deep when one clear input and output hide a lot of work (fit, check, write). It is shallow when the reader must know nearly as much as the code does: five knobs, three hidden inputs, a run order in someone's head.

**Seam.** The place where one step's `outputs/<stem>/` files meet the next step. The seam is the file contract: names, columns, units, keys. Where a seam goes is a design decision of its own.

**Adapter.** A thing that fits an interface at a seam. A script that reads an old `run_*` folder and writes the table the next step expects is an adapter. One adapter makes a hypothetical seam. Two make a real one: do not add a seam that only one thing varies across.

**Leverage.** What callers get from depth. One step that every downstream script reads, with one table layout, pays back N times.

**Locality.** What maintainers get from depth. A change to the filter, a bug in the join, or a question about a seed lands in one place instead of five copies.

## Tests

**Deletion test.** Imagine deleting the step. If its complexity vanishes, it was a pass-through. If the same code reappears in several scripts, it was earning its keep. A "reappears" answer is the signal that a step is worth deepening, not removing.

**The interface is the test surface.** A check reads the step's output file, the same way the next step does. A check that needs the script's internal variables tests past the interface, so the step is probably the wrong shape.

## The lab's rules, as structure rules

- A named function only at 3 or more calls in a script, or when 2 or more scripts share it. Fewer calls: write it inline.
- Scripts compute, notebooks show. A notebook that fits a model or writes a table holds a module that belongs in a script.
- One palette and one theme source (`code/theme.R`, `code/theme.py`). A hex list in a second script is a second source.
- Knobs at the top, UPPER_SNAKE, with a reason beside each.
- A script owns `outputs/<stem>/` and nothing else, and a rerun overwrites it. Reading another step is done from `outputs/<step>/`, by name.

## Smells in these terms

| Smell | Reads as |
|---|---|
| Reads through `dirname(input)` or `RUN_DIR` | The seam is hidden: the interface includes a folder layout nobody wrote down |
| Fan-in over two steps | Shallow join: the step's interface is the sum of its inputs |
| Same 8+ lines in two scripts | No locality: a fix must be made twice |
| Notebook that computes | A module in the wrong place; no seam between compute and display |
| Script with no Snakefile rule | The run order is part of the interface and lives only in memory |
| Step with no check | Nothing tests through the interface |
| Threshold in the middle of a script | A knob hidden in the implementation, and often an impactful choice |

## Why it matters here

There is rarely a metric or gold standard. Results are judged from figures. A structure that keeps each step's inputs, outputs and knobs in plain view makes the figures and the table behind them easier to trust and to re-check. A restructure is safe when the outputs stay byte-identical. It is the user's call when they would change.
