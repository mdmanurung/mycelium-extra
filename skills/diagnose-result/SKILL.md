---
name: diagnose-result
disable-model-invocation: true
description: Find why an analysis result looks wrong, unstable or slow, or why a step fails, with a feedback loop, ranked hypotheses and one probe each.
---

# Mycelium Extra: Diagnose result

A loop for a result that looks wrong, surprising or unstable, and for a step that fails or got slow. Build a tight check first. Everything after it only uses that check. Adapted from Matt Pocock's diagnosing-bugs skill (MIT).

You usually have no gold standard. The signal is then a saved figure you have opened, or a difference between two states you can name. Both count, if you can run them again.

## Rules that hold in every phase

- **Impactful choices are the user's.** A change to preprocessing, a filter, a threshold, a model, a covariate or a seed can change a headline estimate. During diagnosis it is a test, never a fix. Run it as a labelled probe, show the result, and stop and ask before it enters the analysis. A real fix of that kind needs its own approved plan row.
- **Plot-first.** A conclusion cites a saved figure you have opened. If none exists, write `unsupported: no inspected figure`. A figure you only looked at in a viewer does not count; save it.
- **Redact before you show.** Remove secrets and tokens in paths. Do not show donor or patient IDs that could identify a person, or genotype data. Show counts and pseudonymous labels (`donor_03`). If redacted output cannot settle the question, say so and ask.
- **Tag every debug output.** Pick one prefix, for example `[DEBUG-a4f2]` in log lines and `debug-a4f2_` in file names. Write probe files and scratch reruns to a scratch folder outside `outputs/<stem>/` and outside the gated paths, for example `scratch/<prefix>/` in the analysis folder. A step overwrites its own `outputs/<stem>/`, so a debug file there is lost on the next run. Cleanup is then one grep.
- **Do not touch what you do not own.** Never write to `.living/`. Never edit gated code (`analysis/**`, `nbs/**`) without an approved plan. Probes that need code go in a scratch copy, or in a script outside the gated paths.

## Phase 1: Build a loop

This is the skill. A loop is one command that gives the same verdict each run and can go red on this symptom. Spend most of the effort here. [references/loops.md](references/loops.md) lists the kinds of loop for analyses and how to tighten them.

Pick the first that fits:

Reruns of an analysis step are runs. They need an approved plan, or an exploratory run the user allowed (`allow explore`, see `docs/commands.md`). Ask first. Before any rerun, copy the output you are diagnosing into the scratch folder, so the symptom state survives.

1. A failing check on one step's output (a count, a range, a key that must be unique).
2. A rerun of one step on the smallest set of whole units (donors or batches) that still shows the symptom, seeded.
3. A replay of a saved intermediate from `outputs/<stem>/`, not a rerun of the steps upstream.
4. A differential loop: old against new after a code or parameter change. Find the change in `logs/CHANGES.md`, get the old state from git, and compare tables with the script below.
5. Bisection over code states, or over data subsets.
6. A permutation or simulated-null loop, when the result is only sometimes wrong.
7. A figure you must look at. Last resort. Save it, open it, and write down what you saw.

Phase 1 is done when you can name one command you have already run, and its output shows the exact symptom. If no loop can be built, say so, list what you tried, and ask for what you need: access to the data, a saved intermediate, a before-and-after pair. Do not guess at causes without a loop.

For a result that varies between runs, raise the reproduction rate first: fix seeds, then repeat 20 times and count how often it shows.

## Phase 2: Reproduce and minimise

Run the loop and confirm it shows the symptom the user described, not a neighbour of it. Then cut one thing at a time (donors, genes, steps, parameters) and rerun. Stop when removing anything makes the symptom vanish. Keep the cut list.

## Phase 3: Hypothesise

Write three to five ranked hypotheses. Each states a prediction: "If X is the cause, then changing Y removes the symptom, and changing Z makes it worse." A hypothesis with no prediction is dropped or sharpened. [references/hypotheses.md](references/hypotheses.md) is a catalogue to prompt from, not a list to run.

Show the ranked list to the user before testing. They often know what changed or what is ruled out. Do not block on it if the user is away: test your top hypothesis and show the list with the result.

## Phase 4: Probe

One probe per hypothesis, one variable at a time, each tagged. Prefer a saved figure or a count at a boundary over printing everything. For a slow step, time it first and bisect the cost. Do not read logs for causes: they are usually wrong or silent. Measure, then bisect.

## Phase 5: Fix and check

Turn the minimal repro into a regression check at a seam where the real pattern occurs, and place it outside the gated paths (for example `tests/`). Watch it fail. If you forced the red by editing code or a fixture, diff against a pristine copy to prove the edit landed before you trust the failure. Then apply the fix, watch it pass, then rerun the Phase 1 loop on the original scenario. A fix that edits gated code needs an approved plan and a rerun through `run.sh`.

If no correct seam exists, that is the finding. Say what blocks the check, for example a step that mixes loading, filtering and fitting.

## Phase 6: Clean up

- The Phase 1 loop no longer shows the symptom.
- The regression check passes, or the missing seam is written down.
- `grep -rn "DEBUG-a4f2" .` and `find . -name "debug-a4f2_*"` (with your prefix) find nothing.
- Scratch copies are deleted.
- The confirmed cause is stated in one sentence for the analysis log, with the figure that supports it.

## Compare two tables

Read-only. Exit 0 identical, 1 different, 2 unusable input (missing file, missing or empty key, duplicate keys or column names, a row wider than the header).

```bash
sh <skill-dir>/../../hooks/py.sh - OLD NEW --key donor,gene [--rtol 1e-6] [--atol 1e-8] [--max-rows 10] [--redact-keys] < <skill-dir>/scripts/diff_tables.py
```

It reports rows and columns present on one side only, type-like changes (integer, number, text) and numeric differences beyond the tolerances, with the first rows that differ. It also reports a changed column order. Text compares exactly, so `007` differs from `7` and `NA` from an empty cell. An infinite value differs from anything but itself. Use `--redact-keys` when keys are donor IDs: it hides key values, text cell values and column names (rows and columns show by position).
