# Stay oriented: focus and track changes

`focus` says which analysis this session is working on. `track-changes` shows what moved away from what you approved. Neither approves, freezes, runs or validates anything.

![Focus names the analysis for the current session. Track changes compares approved intent and observations. The Journal exposes historical records and explicit coverage; none of these judges scientific impact.](../figures/orientation.svg)

Focus supplies context, not ownership or approval. Open one observation to inspect evidence; whether a change matters scientifically remains your decision.

## What you control here

- **Your typed word:** every `focus` line. The agent has no command that changes a focus. `freeze <hash>` after reading a report is also yours.
- **Shown to you:** the focus card, and the track-changes card with a Markdown brief and an offline HTML report.
- **To turn it off:** `focus end`. Never type `focus` and none of it runs. The turn-end focus notice is off unless `gate.json` sets `"focus_notices": true`.

## Steps

1. Start a focus on a folder under a gated root (`analysis/` and `nbs/` by default). Type each line as the whole prompt:

   ```text
   focus analysis/vaccine-response
   focus analysis/vaccine-response plan 84bb5fce
   focus status
   focus switch analysis/other
   focus end
   ```

   The folder must exist. A plan is linked only if you name it, and only if its table names a path inside the folder. `/mycelium-extra:focus` lists the folders you can name.
2. Run `track-changes` on the folder:

   ```text
   /mycelium-extra:track-changes analysis/vaccine-response
   ```

   It uses this session's open focus, or the folder you name. If several approved plans name paths inside it, it asks which one states the original intent: pass `--original <hash>`. It never picks by date.
3. Read the card: Baseline, Attention, Also, Unknown. Open `report.html` from `.mycelium-extra/track-changes/<analysis>/` in a browser; `brief.md` is the same evidence as one file you can hand to a reviewer.
4. For the evidence behind one item, ask for it by id (ids are in `brief.md`; a unique prefix works):

   ```text
   /mycelium-extra:track-changes analysis/pbmc-ifn --explain P-9bfd9b23
   ```

   It prints Observed, Potential, Unknown, Authorization and Evidence, reads the same records, and writes nothing. Under the hood the flag is `track_changes.py --explain <item_id>`.
5. Decide: review the diffs then `freeze <hash>`, revise the plan with `grill`, or `verify report <hash>` for failed runs. None of these run from the report; its buttons only copy text.

An [example report.html](../examples/track-changes-report.html) shows the report itself: real output on a synthetic analysis, one offline file.

## Worked example

Real output from `tests/e2e/make_track_changes_example.py`, regenerated for this page on a synthetic analysis (`analysis/pbmc-ifn`, invented names, no data). The plan's cell threshold was changed from 500 to 200 and re-approved, with one failed run and its retry. The card:

```text
mycelium-extra · track-changes analysis/pbmc-ifn · snapshot 10-19 21:58
Baseline   original 5b50b8f9 · current 813cc324 (instance ad3c02c6) (newest approved plan naming this folder; --current to choose)
Attention  2
  ⚠ Plan step 1 choice: minimum 500 cells per donor → minimum 200 cells per donor
  ⚠ Execution record: 3 run(s), 1 failed, 0 unmatched
Also       1 authorized change(s) · 1 routine
Unknown    shell-made edits; file reads; scripts no approval pinned and no run touched; edits to other analyses (no transcript read) · 2 coverage limit(s) in the brief
▶ decide whether the plan change is intended; `/mycelium-extra:grill` revises it
Files      .mycelium-extra/track-changes/analysis__pbmc-ifn (brief.md, report.html: open the HTML in a browser)
```

And `--explain P-9bfd9b23` on the first item (ids differ from run to run):

```text
Observed
  Row 1, choice: was `minimum 500 cells per donor`, now `minimum 200 cells per donor`.

Potential
  Potential analytical implication: a changed Choice, Step or Validation can change what is estimated; whether it does is for the researcher to assess.

Unknown
  Why the plan changed is not recorded here.
  not observed anywhere in this report: shell-made edits; file reads; scripts no approval pinned and no run touched; edits to other analyses (no transcript read)

Authorization
  The current plan was approved by the researcher, so this is a later authorized revision, not an unexplained deviation.; focus relation within_path; difference observed

Evidence
  E-35956ef1 approval 5b50b8f9 original plan approved 10-19 21:58
  E-63898f96 approval 813cc324 current plan approved 10-19 21:58
This block approves, freezes and validates nothing; it does not say whether the change matters.
```

Notice the wording: an observed change, a potential implication, an unknown. It never says "safe" or "in scope".

## What this does not guarantee

No warning is not evidence of no drift: shell-made edits, file reads and unmarked subagent work are not observed, and edits to other analyses need a recorded Claude Code transcript (other hosts have none). A changed number is an observed edit, not a changed conclusion. Reports hold code diffs and live under `.mycelium-extra/`, which should be git-ignored. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[focus](../reference/skills/focus.md) · [track-changes](../reference/skills/track-changes.md) · [Focus and track changes, in full](../focus-and-track-changes.md) · next: [hand off](hand-off.md)
