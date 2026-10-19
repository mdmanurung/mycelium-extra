# Focus and track changes

Two small tools for long analyses. **`focus`** says which analysis this session is working on. **`track-changes`** shows what moved away from what you approved. Neither approves, freezes, runs or validates anything: the gate, `freeze` and `verify` keep that role.

## Focus

Type each line as the whole prompt. The gate answers it, so the agent never runs it.

| You type | What happens |
|---|---|
| `focus analysis/pbmc-ifn` (or `focus nbs/09_factorizations`) | Starts a focus on that folder. It must exist under a gated root: `analysis/` and `nbs/` by default, otherwise the folders in `gate.json`'s `gated_paths`. Refused if one is already open or the folder is missing (it lists the folders that exist). |
| `focus analysis/pbmc-ifn plan 84bb5fce` | Same, and notes that approved plan `84bb5fce` states the original intent. Refused unless that plan's table names a path inside the folder. |
| `focus status` | A short card, shown to you only. |
| `focus switch <folder>` | Ends this focus and starts the next. The first stays in the record. |
| `focus end` | Closes it. The analysis is not thereby complete or reportable. |

```text
mycelium-extra · focus analysis/pbmc-ifn · since 10-19 09:12
Objective  Characterize interferon response in PBMC. (analysis/pbmc-ifn/PBMC_IFN.md)
Plan       original 84bb5fce (selected)  ·  newest approved naming this folder: aabbccdd
Runs       not authorized in this session (an active approval belongs to another session)
Next       /mycelium-extra:track-changes analysis/pbmc-ifn   ·   focus switch|end
```

What to rely on:

- **It grants nothing.** Runs still need an approved plan, exactly as before. The `Runs` row reports that separately and never says focus authorized anything.
- **It is yours to change.** Only the line you type changes a focus; the agent has no command that does. While one is open, each prompt carries one advisory line asking the agent to stay on that analysis and to propose `focus switch` rather than drift. You can still ask it anything.
- **One per session.** Two terminals can focus different analyses. A new session starts with none: `handoff` suggests the line to type.
- **Nothing is guessed.** The folder must exist and sit under a gated root. A plan is linked only if you name it. The objective is quoted from the analysis doc, or reported as not stated.
- State is one small file per session in `.mycelium-extra/focus/` (no prompt text). A malformed file is reported, never repaired.

## Track changes

```text
/mycelium-extra:track-changes [analysis/pbmc-ifn]
```

It uses this session's open focus (from `$CLAUDE_CODE_SESSION_ID`, or `--session`); a focus an earlier session left open is never picked up. Without one, name the folder. If more than one approved plan names a path inside it, you are asked which states the original intent (`--original <hash>`, or type `focus <folder> plan <hash>` once); dates are not used to guess. On a broad folder that many plans name, focus a deeper folder instead.

```text
mycelium-extra · track-changes analysis/pbmc-ifn · snapshot 10-19 11:02
Baseline   original 84bb5fce · current aabbccdd (instance 1a2b3c4d)
Attention  3
  ⚠ Plan step 1 choice: min_cells 500 → min_cells 200
  ⚠ analysis/pbmc-ifn/scripts/01_fit.py edited since approval aabbccdd
  ⚠ Observed work under analysis/other-classifier while analysis/pbmc-ifn was in focus
Also       1 authorized change(s) · 2 routine
Unknown    shell-made edits; file reads; subagent work not marked in the transcript
▶ review the diffs, then `freeze aabbccdd`   (or `/mycelium-extra:grill` to amend the plan)
Files      .mycelium-extra/track-changes/analysis__pbmc-ifn (brief.md, report.html: open the HTML in a browser)
```

It reads, and only reads:

| Source | What it shows |
|---|---|
| Approved plans | Row-by-row changes from the original to the current plan, and a changed objective. A later approved plan is an authorized revision, not an unexplained deviation. |
| Approval pins and kept snapshots | Each script against what the original and the current approval pinned, with a bounded diff. No kept snapshot means no diff, never an invented baseline. |
| Re-pin journal | How often a script was re-pinned since the approval. |
| Receipts | Failed runs and retries (both kept), runs with no matched launch, `sbatch` submissions (submission only), runs under another approval instance. |
| Declared outputs | Files older than the newest code change. A file time never shows the code produced the output. |
| A Claude Code transcript (optional) | Direct Edit/Write calls to another analysis after the focus started. |

Every item separates what was **observed**, what is only a **potential analytical implication**, and what is **unknown**, and carries independent labels (difference, focus relation, authorization, consequence, attribution, currency; see [the schema](../skills/track-changes/references/schema.md)). A changed number is an observed edit, not a changed conclusion. Another analysis's folder may be a supporting dependency, so it is called "relationship not established", not "off task".

The HTML report has Review, Diff, Timeline and Evidence tabs, filters and search. It is one offline file: no network, no scripts from elsewhere, and its buttons only copy text (for example `freeze aabbccdd`). Nothing in it can run a command.

### Limits

- **No warning is not evidence of no drift.** Shell-made edits, file reads and subagent work not marked in the transcript are not observed; every report says so.
- Cross-analysis edits need the transcript recorded at the focus start (or `--transcript`); other hosts have none.
- Plan inputs, outputs and validation blocks are not compared here; use `verify diff <old> <new>`.
- Reports hold code diffs. Strings that look like keys, tokens or passwords are replaced by `[redacted]`, which is a heuristic, not a guarantee. They live under `.mycelium-extra/`, which should be git-ignored; the command warns if it is not.
- Reports are regenerable views, not records. `verify` stays the authority on what the runs establish.
- The viewer was exercised in Node against a DOM stub, not in a browser. Open `report.html` once from disk on your own machine.
