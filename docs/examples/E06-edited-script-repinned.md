# E06. A one-line fix after a failed run: re-pinned, shown, re-approved

Control point: **override**

Anonymised from a real project. Source: a revised plan in project B ("step 1 ran once, passed its check, then crashed; one line now builds a numeric matrix first; the script is gate-pinned, so the edit needs re-approval"). At that time (0.9.44 behaviour) the gate blocked the run until re-approval. Since the release that reversed this (see CHANGELOG, "An edit to a script the plan lists no longer blocks a run") the gate re-pins and shows the change. The notices below are the current ones, regenerated on the fixture.

## 1. Socratic: ask these first

- What did the plan say this step does, and which line moved?
- Does the change touch the choice I approved (a model, a threshold, a count) or only plumbing?
- What stays unknown after the diff: which other code does the script source?

## 2. What the tool showed

On the first run after the edit (current release):

```text
mycelium-extra: analysis/example/scripts/02_paired_test.py re-pinned under plan <hash> (+3 -0 lines). Runs now use the new version; `freeze <hash>` shows the diff.
  numbers changed: new 2000 (not in the plan)
  If this is another choice than step 2 states, say so; the plan is not edited for you.
  Other changed lines: 1
```

The revised plan's card opens with the change:

```text
  Scripts changed since last approved
    • analysis/example/scripts/02_paired_test.py: sha256 4df348ce01ab -> sha256 2165381b99b0 (+3 -0 lines)
Since <hash> (approved <date>)
  scripts  CHANGED: analysis/example/scripts/02_paired_test.py · SAME: .../01_select_samples.py
  plan     objective SAME · steps: 1 same, 1 new or changed
4 changed-script diff line(s): `card <new hash> diff`
```

## 3. Track-changes card (regenerated)

```text
mycelium-extra · track-changes analysis/example · snapshot <time>
Baseline   original <hash> · current <hash> (instance <id>)
Attention  3
  ⚠ Plan step 2 choice: median-of-ratios; exact permutation; BH… → median-of-ratios; exact permutation; BH…
  ⚠ analysis/example/scripts/02_paired_test.py differs from the original approved code
  ⚠ 1 declared output(s) older than the latest code change
Also       0 authorized change(s) · 1 routine
Unknown    shell-made edits; file reads; ... edits to other analyses (no transcript read)
▶ decide whether the plan change is intended
```

Reading it: Observed code change in one script. Potential analytical implication: the new number appears in no plan row. Execution evidence gap: the earlier output is older than the code. Relationship to the current focus not established. It never says the change is safe.

## 4. Librarian block

None.

## 5. What the human decided

Approve the revised plan. The plan also declared a decision rule before any result ("single-donor driven if ... otherwise not"), so the result could not choose its own threshold.

## 6. Without the tool

The edited script would have run under an approval written for the old version, with no diff in front of the researcher.

Basis: re-pin / "what changed since" plans: 7 of 144 approvals; this one chosen.
