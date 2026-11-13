---
name: improve-structure
disable-model-invocation: true
description: Review how one analysis folder or lab repo is organised and propose up to five deepening candidates, then hand the pick to grill.
---

# Mycelium Extra: Improve structure

A read-only review of how analysis code is organised. It finds friction, shows up to five candidates on a one-off page, and hands the one you pick to `/mycelium-extra:grill`. It never edits code and never moves outputs. Adapted from Matt Pocock's improve-codebase-architecture skill (MIT).

Use the words in [references/vocabulary.md](references/vocabulary.md) exactly: module, interface, depth, seam, adapter, leverage, locality. Read it first.

## Rules that hold in every step

- **Read-only.** No edits to `analysis/**`, `nbs/**`, `code/`, `outputs/` or `.living/`. The page goes to a scratch folder or the Artifact tool, never into the repository.
- **Restructuring changes nothing the reader sees, or it is a plan row.** A candidate may only move code so that outputs stay byte-identical. A candidate that could change a headline estimate, a ranking, a selected feature or a conclusion (a filter moved, a transform merged, a seed shared, a threshold unified) is the user's choice and needs its own approved plan row. Mark it on the card.
- **Plot-first.** A claim about a result cites a saved figure you opened. With none, write `unsupported: no inspected figure`. Structure claims cite files and lines.
- **No interfaces yet.** Candidates name the friction and the direction. The interface is designed in grill.

## 1. Scope by hot spots

If the user named a direction (a step, a folder, a pain), take it. Otherwise find where the code keeps changing, because deepening pays off where change is frequent:

- `git log --name-only --format= -- code | sort | uniq -c | sort -rn | head` inside the analysis (use a script file if the approval gate blocks the pipe).
- `logs/CHANGES.md`: the `Code changed:` lines show which scripts get edited run after run.

Say which folder or steps you chose and why, in one line. If the changes are scattered, widen the scan to the whole folder. Read the analysis doc, `plans/PLAN.md` and `GLOSSARY.md` when present, so names match the lab's words. A closed decision in `.living/decisions.md` is not reopened.

## 2. Scan

```bash
<skill-dir>/../../hooks/mxpy - PATH [--json] < <skill-dir>/scripts/scan_structure.py
```

`PATH` is an analysis folder or a folder of analyses. The script is read-only and prints a text summary (or JSON). It reports:

| Finding | Meaning |
|---|---|
| `shared_folder_read`, `absolute_step_path` | A step reaches another through `dirname(input)`, `RUN_DIR`, `base_dir` or a hard-coded path |
| `fan_in` | A script reads more than two other steps' outputs |
| `duplicated_block` | 8 or more identical lines in two scripts |
| `long_script`, `long_pipe` | Over 300 lines, or a chain over 15 lines |
| `heavy_notebook` | A qmd, Rmd or notebook fits models or writes tables |
| `no_snakefile`, `no_rule` | A numbered script no Snakefile rule runs |
| `no_check` | A step with no Validation cell in a plan table and no check file |
| `midscript_parameter`, `knob_not_at_top` | Thresholds, counts, seeds or knobs set after the data read |
| `plot_without_theme`, `palette_repeated` | Plot code that skips the shared theme, or hex palettes written out twice |
| hot spots | The code files edited most, from git and `logs/CHANGES.md` |

A finding is a place to look, not a verdict. Open the files. Then apply the **deletion test** to each suspect module: would deleting it concentrate complexity or just move it? Drop findings that fail it. Ignore a duplicate that the lab rule allows (fewer than 3 calls in a script and fewer than 2 scripts sharing it). The scan misses what only reading shows, such as one step doing two jobs or a seam that carries a hidden run order.

## 3. Present up to five candidates

Order them by strength: **Strong**, **Worth exploring**, **Speculative**. Fewer than five is fine. Write the page with the Artifact tool, following [references/card-page.md](references/card-page.md). An Artifact is a private one-off page; the repository's record is the analysis doc, not this page. Each card holds:

- **Files**: the scripts and notebooks involved.
- **Problem**: one sentence on what hurts.
- **Proposed change**: one plain sentence. No interface.
- **Benefit**: in leverage, locality and testability terms.
- **Before and after**: a diagram of steps and the seams between them.
- **Outputs check**: whether the change can keep outputs byte-identical, and if not, the plan row it needs.
- **Strength**.

Give the page link and ask: "Which would you like to explore?" If the page cannot be made, give the same cards as text.

## 4. Hand over to grill

When the user picks one, tell them to run `/mycelium-extra:grill` with the candidate as the task. Give grill the card text, the files, and this check for the plan's Validation column: rerun the affected steps before and after the change and compare each table with `/mycelium-extra:diagnose-result`'s `scripts/diff_tables.py` when present. Figures are compared by opening both. A byte-identical result is the pass. Any difference is a finding for the user to judge, not a failure to hide.

The change itself runs through the approved plan. This skill ends at the handover.

## 5. Keep what is worth keeping

- A card the user rejects for a load-bearing reason ("these two steps look alike but must stay apart because ...") can go to `/mycelium-extra:decision-status` after the user confirms. Offer it once. Skip passing reasons such as "not now".
- A term the user settles while choosing goes to the `glossary` skill when it is present. Otherwise name it in the grill brief's Terms to record.
- Write nothing to `.living/` yourself.
