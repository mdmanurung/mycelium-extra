# Applying these changes to mycelium-extra

Built against `main` at `3a11123` ("docs: add a workflow diagram to the README"). This file is not part of the change; do not commit it.

## What is in this folder

- `patches/`: 24 commits from `3a11123` to version 0.9.31. Apply them with `git am`. This is the source of truth.
- `mycelium-extra-improvements.bundle`: the same commits as a git bundle (needs `3a11123` in your clone).
- `changed-files/`: the final content of every file the series adds or changes, at repository paths, for reading on GitHub or in an editor. Nothing is deleted.
- `notes/`: the build notes for each workstream: test commands and results, negative tests, design reasons, and open questions. `e3-v1.md` is the first E3 attempt, which was replaced. It is kept for its E3b design.
- `tools/`: `check_links.py` (relative links and GitHub anchors) and `check_preserve.py` (no README content lost in the T0 split). CI (A2) can use these.
- `pending/d1-design/`: the D1 design and draft skill. Commit them under `docs/design/` when D1 starts.
- `c1_feasibility_probe.py`: the stdlib probe behind the C1 simulated-data numbers. It is not meant to be committed; `tests/fixtures/make_fixture_data.py` now does the same job.

## Steps

```bash
cd mycelium-extra
git switch main && git pull
git log -1 --format=%h          # expect 3a11123; if later, use `git am -3` and resolve
git switch -c improvements
git am "$SRC"/patches/*.patch
for t in $(git ls-files | grep 'tests/test_.*\.py$'); do printf "%s: " $t; python3 $t 2>&1 | tail -1; done
python3 hooks/tests/gate_diff.py --base 3a11123   # 24/148 differ, all in receipt state; no decision changes
git push -u origin improvements  # then open a PR
```

Alternative: `git fetch "$SRC/mycelium-extra-improvements.bundle" all-improvements:improvements`.

To land fewer changes, apply a prefix of the series, or drop commits with `git rebase -i`. Commits 0001-0003 are the earlier grill checklist and roadmap work. The single version bump (0022) can be split per feature if you keep the one-feature-two-commits rule. The doc-sync commit (0021) follows the code commits it describes.

## Commits

| # | Commit | Task |
| --- | --- | --- |
| 0001 | feat(grill): LLM failure-mode checklist | D5 |
| 0002 | docs: add improvement roadmap (and the C1 design) | roadmap |
| 0003 | chore: bump version (0.9.29) | |
| 0004 | docs: split the README into a landing page plus docs/ | T0, B1 |
| 0005 | docs(handoff): point the dev rules at docs/development.md | B3 |
| 0006 | docs: say in the summary table that plan-review sends a packet off the machine | B4 |
| 0007 | docs: add an MIT license | A1 |
| 0008 | docs: add a changelog and make it part of the version bump | A3 |
| 0009 | docs(roadmap): record that A4 is drafted and awaits the maintainer | A4 |
| 0010 | test(verify): scrub host environment in verify tests | test fix |
| 0011 | fix(gate): pass state-folder mentions that only name text | E2 |
| 0012 | fix(gate,verify): take the Bash exit status from the hook event | E3c |
| 0013 | fix(gate): resolve sbatch --wrap payloads against -D/--chdir | E3a |
| 0014 | docs(verify): state that runs under Codex are not receipted | E3d |
| 0015 | feat(data-contract-check): read h5ad obs and warn on graded batch imbalance | D6 |
| 0016 | feat(plan-review): flag defaults without a reason | D9 |
| 0017 | feat(verify): report unexplained defaults in the frozen plan | D9 |
| 0018 | docs(grill): unstated defaults are partly checked by verify | D9 |
| 0019 | test(e2e): add the fixture project and its data generator | C1 build step 1 |
| 0020 | test(e2e): add the harness and the baseline chain test | C1 build step 2 |
| 0021 | docs: sync the gate, verify, and data-contract docs with E2, E3, D6, and D9 | docs, HANDOFF, CHANGELOG |
| 0022 | chore: bump version to 0.9.30 | |
| 0023 | fix(verify,new-analysis): survive a non-UTF-8 locale on Python 3.6 | review blocker |
| 0024 | chore: bump version to 0.9.31 | |

## Checks already run (on a fresh clone of 3a11123 with all 24 patches)

- **Test suite:** all 12 test files pass on a real **Python 3.6.8** interpreter, with and without the host's conda and virtualenv variables. Before 0023 `tests/test_end_to_end.py` failed on 3.6: `verify` and `new-analysis` both raised on the harness's `LC_ALL=C`, because Python 3.7+ hides this by coercing the C locale to UTF-8 (PEP 538). Before 0010, `test_verify.py` failed 3 tests on any machine that exports `CONDA_PREFIX`. `test_gate.py` skips 1 test because no Python 3.6 is installed.
- **Python 3.6 grammar:** every changed `.py` file parses with `ast.parse(..., feature_version=(3, 6))`. No 3.6 interpreter was available to run them.
- **gate_diff:** `gate_diff.py --base 1db67c1` gives 124/148 identical. All 24 differences are receipt state (the new `exit_source` field, `exit_status` values, and `sbatch --wrap` paths). No allow or deny decision and no message changed. The three intended E2 changes are not among the gate_diff cases; the new tests in `test_gate.py` cover them.
- **Links:** 31 relative links and anchors across README, HANDOFF, CHANGELOG, `docs/`, the roadmap, the design and the fixtures README; none broken.
- **Branch match:** the series applied to clean `3a11123` gives the same tree as the build branch, and the bundle verifies.
- **Negative tests (details in `notes/`):** each new test was checked by reverting its fix or breaking its input, and each then failed.
- **h5ad and R:** the h5ad tests ran with h5py 3.14; without h5py they skip, and a separate test checks that a missing h5py is a gap. The C1 chain test passes both with R and without R on PATH, in about 10 s.

## Decisions for the maintainer

1. **License (A1):** MIT, "Copyright (c) 2026 Mikhael Dito Manurung", because every commit is dated 2026. The plugin manifests say "Mikhael Manurung"; pick one name.
2. **Tags (A3):** no tags were created, and the maintainer deferred them (2026-10-04). `notes/docs.md`
   now has all 16 commands; its v0.9.29 sha was wrong (`1db67c1` never existed outside a deleted
   scratch clone) and is now `4f5ab08`, whose subject is just "chore: bump version". v0.9.30 is
   `49f9154` and v0.9.31 is `573fbdb`; all three are safe now that `main` fast-forwarded to the series.
3. **Description and topics (A4):** run
   `gh repo edit mdmanurung/mycelium-extra --description "Planning, approval gate, and provenance checks for AI-agent analysis work; complements Mycelium in Claude Code and Codex." --add-topic claude-code --add-topic codex --add-topic llm-agents --add-topic reproducibility --add-topic provenance --add-topic bioinformatics --add-topic research-software --add-topic mycelium --add-topic ai-agents`
4. **E3c exit status.** The Claude Code hooks reference says `PostToolUse` fires only after a tool succeeds, and a failure fires `PostToolUseFailure` with a first line `Exit code N`. The plugin did not register the second event, so a failed run left no receipt at all. Now:
   - a `PostToolUse` receipt records exit 0 from the event;
   - a failure records N, `failed` or `interrupted`, and verify treats it as a failure;
   - a background start, or a payload without an event name, is `unknown`, which is a gap.

   Open points:
   - Resolved (2026-10-04): old receipts with a null exit status stay a **gap**. The 3a11123 gate
     read the exit code from the tool response only, with no background or interrupt flag, so a
     null cannot tell "finished OK" from "only started" or "cut off". No code change; the `else`
     at `verify.py:689-692` keeps covering both `None` and `"unknown"`.
   - The `backgroundTaskId` response key is a guess; only `run_in_background` is documented.
   - Mycelium's post-action hints are also sent on failure events.
5. **D6:** exit code 3 is new and means "gap, nothing blocking". On a per-cell `.h5ad` `obs`, unit checks and `max_share` count cells, not samples.
6. **D9:**
   - The minimum reason length is 3 words. This keeps the fixture's `default: matches step 2` clean.
   - A missing checker makes verify report a gap (CONFORMS_WITH_GAPS), following the scilintr precedent. If the status should stay unchanged, it is a one-word change.
7. **sbatch `-o`/`-e`/`-i`:** values under gated paths are probably denied wrongly (found during E3a and left unchanged).

## Not done yet

- **E3b** (a Snakemake rule's inputs counted as runs): `notes/e3-v1.md` has a design that decodes `script:` targets with `pickletools` without unpickling. The roadmap E3 Status line says `partial`. HANDOFF keeps this one known receipt gap.
- **gate_diff scenarios** for the three E2 commands and their write-shaped twins.
- **C1 build steps 3 to 5:** defect layers, catalog tests and `ablate.py`.
- **B2** (move the dated verify history to the changelog). A3 has landed, so B2 is no longer blocked.
- **Finding for C1 step 4:** with output times not spaced, verify credits `de_results.tsv` to run 01 and still says CONFORMS. It does not notice an output credited to the wrong run of the same plan. Add this as a known-miss case.

## Design corrections made while building C1 (also in `docs/design/c1-fixture-project.md`)

- The project has 31 files (the Slurm script was missing from the count), and `tests/test_fixture_data.py` is added.
- The TSVs carry no `SIMULATED` header line, because data-contract-check would read a `#` line as the header. The manifest, data dictionary and raw-data note say SIMULATED instead.
- The `expected/` files come with commit 1. `summary.tsv` is computed in Python and checked against real R output.
- Hook events: a success is `PostToolUse` with no exit code, and a failure is `PostToolUseFailure`. The harness reads `hooks.json` to decide which events it can send.
- Timing: verify credits an output to the earliest run within 5 s before it, so the harness spaces output modification times with `os.utime` and never sleeps.
