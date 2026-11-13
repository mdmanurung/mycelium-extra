# DATA branch

Question: does this method, threshold or model behave sensibly? Read this when SKILL.md step 1 picked DATA.

## Build

1. **A table with known truth.** Simulate a toy table where you set the effect, its sign and the donor spread. The runnable example `examples/prototype_paired_toy.py` is the model: a paired design, 6 donors, true effect +1.0.
2. **One small unit set.** Take whole donors or batches, each with all its rows and controls. Never random rows. Which donors is an impactful choice: ask the user which ones and why, and write it as a proposed plan row. Run the method on the toy table first, then on this set of the real data (read-only, in memory).
3. **One action per block.** Load, filter, aggregate, contrast. Each block ends in a printed state.

## What each state print shows

- shape (rows, columns) and units present
- counts per donor, and per donor by condition
- what the step removed, as a number per donor; print `removed 0` when nothing went
- the contrast and its sign, with the direction written out ("treated minus control")
- the method's estimate next to the known truth, on the toy table

Done when each action prints these and a reader can see where a number changed.

## Ask these of the output

- Does the estimate recover the known effect, and with the right sign?
- Does any donor lose most of its rows, or drop out?
- Does the result move when the threshold or option moves? Run it at two or three values and print one line per value.
- Do the donors agree in direction? Donors are the replicates.

A value that moves the estimate is an impactful choice. Write it as a proposed plan row. Do not pick it.

## Keep it small

A cell-level object stays in memory, and the toy run finishes in seconds. A job that needs SLURM is no longer a prototype: shrink the unit set.
