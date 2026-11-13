# where

Shows what is going on in one analysis, shaped for a reader who loses the thread: aim first, then where it stands, then the next action. It reads files and writes one small plugin-state file.

## Synopsis

You type the words; the gate answers before the agent sees them. The typed word needs the gate on and a gated repository. While the gate is off or paused by `/goal`, use `/mycelium-extra:where`. The skill (`/mycelium-extra:where`) runs the same code (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`):

```bash
sh <skill-dir>/../../hooks/py.sh - [short|all] [--no-write] < <skill-dir>/../../hooks/whereami.py
```

## Typed commands

Send each as the whole prompt. A sentence that merely starts with "where" is an ordinary message.

| You type | Card |
|---|---|
| `where`, `where am i` | Full card: aim, right now, do next with a time estimate, approach checklist, later, watch out. |
| `where short` | The name, then five lines: aim, state, next, then, block. |
| `where all` | One line per analysis under a gated root, newest activity first. When there are none, it looks one level below the gated roots and next to the current folder, and names the roots it searched. Only the newest eight are scanned; the rest show as `+N not scanned`. |

The analysis is the open `focus` folder, else the analysis folder of the current directory (the nearest folder above it with `code/` and a Snakefile, `plans/` or `outputs/`).

## The full card

```text
WHERE YOU ARE: demo

AIM
  not written: open work/demo/DEMO.md

RIGHT NOW
  Step 2 of 4. 1 of 4 steps current.
  02_fit.py changed 49 min ago. Stale: 02, 03, 04.
  Assumes steps run in number order.

DO NEXT  (about 2 min)
  1. bash run.sh
  2. Open outputs/03_show/figures/03_show.png

APPROACH
  [x] 01_prep
  [~] 02_fit
  [~] 03_show
  [~] 04_page

LATER
  - S01: code/01_prep.R
  - S02: code/02_fit.py
  - S03: code/03_show.R
  - S04: code/04_page.qmd
```

This card came from a real run on a copy of the smoke analysis after `code/02_fit.py` was edited.

A card for a current analysis whose outputs changed after the last verify (output of `whereami.py` on a throwaway analysis, not a real project):

```text
RIGHT NOW
  3 of 3 steps current.
  No run log (logs/CHANGES.md).
  Changed since verify: outputs, 5 min ago.

DO NEXT
  1. Run /mycelium-extra:verify

WATCH OUT
  - Changed since verify: outputs, 5 min ago.
```

Every list holds at most five items; the rest is "+N more".

## Where each part comes from

| Part | Source |
|---|---|
| Aim | the open focus objective, else `## Objective` or `## Purpose` in the analysis doc. A scaffold placeholder counts as not written. |
| Steps | numbered scripts in `code/` against `outputs/<stem>/`. `[x]` current; `[~]` stale, because the script or an earlier step is newer than the step folder; `[ ]` not run; `[!]` after a failed run, the step that has only a `logs/` folder (Snakemake writes `logs/` when a job starts, so it is not output), else the first step not run; no mark when no Snakefile rule names `outputs/<step>/`. A step with a rendered page in `outputs/<step>/` (or an older `reports/<step>*`) counts as run. Order is the number order, so a side-branch script such as `01b_` marks every later step stale; the card says so. Older run-folder and flat layouts get no per-step marks. |
| Do next | in order: a failed last run (read the log of the failed step), stale or missing steps (`bash run.sh`), a waiting plan (`approve`), the first open row of `plans/TRACKER.md`, then `/mycelium-extra:verify` when the verify record is changed, interrupted or missing, else nothing pending. When every step is current, tracker rows that name a current step's script (the scaffold `S` rows) are skipped, and WATCH OUT says so. |
| Verify line | one line under RIGHT NOW (and in the short card's STATE). `Verified 2 h ago.`, `Changed since verify: code, 5 min ago.` (`code`, `outputs` or `log`, whichever changed last), `Verify was interrupted.`, `Never verified.` or `Verify record unreadable.` Only `<analysis>/provenance/PROVENANCE.md` counts; a file of that name elsewhere is ignored. The last data row gives the Verified minute, because verify replaces a re-verified plan's row and appends it. `provenance/.transactions/pending.json` means interrupted. The record is changed when the newest of the last `logs/CHANGES.md` heading, `code/` and `outputs/` falls in a later minute than the Verified cell; the same minute counts as verified, because both stamps are only minute-precise. Step logs under `outputs/<step>/logs/` count as outputs. The line shows for every layout. `where all` skips it. |
| Time estimate | the sum of the last Snakemake benchmarks of the steps `run.sh` would redo; "time unknown" when one is missing. |
| Later | the other open rows of `plans/TRACKER.md` (`todo`, `in progress`, `blocked`). Their status is yours to update. |
| Watch out | a figure with no source data of the same stem, an empty step folder, skipped tracker rows, a changed, interrupted or unreadable verify record, and `stopped counting at N files; state may be wrong` when `outputs/` is too large to scan in about 1.5 s or 5000 files. |
| State word in `where all` | `failed`, `stale`, `not run`, `partial` (some steps current, the rest not run), `current`, `no steps`, or the status of an old-layout run. The last-run column reads `no run log` when steps have output but `logs/CHANGES.md` is missing, and `run time unreadable` when its newest heading has no valid time. |

## Reads and writes

Reads the analysis folder and the focus record. Writes `.mycelium-extra/now/<analysis path, "/" as "__">.md` with the full card each time it is shown (`--no-write` skips it). Nothing is written into the analysis folder, and no gate state changes.

## When it fails

A typed `where` that cannot build its card is blocked with one line naming the error and the analysis; run `/mycelium-extra:where` to see the full message.

## OpenCode

The card is shown as a blocked-prompt reply. On OpenCode that reply is passed to the model as the rewritten prompt, so it can still cost a model turn. On Claude Code no model call runs.
