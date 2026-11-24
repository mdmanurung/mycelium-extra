# 19 · Review and benchmark-driven refinement (2026-11-24)

[Back to roadmap](README.md)

Objective: review the package at `789d7d6` (0.36.1), then improve it against a frozen, deterministic benchmark instead of reviewer opinion. A later tusoskill run uses the same benchmark as its evaluator. Status: **approved 2026-11-24** (user: "Approve all", rows B0-B9 and choices C1-C5 as recommended).

Statuses: `todo`, `in progress`, `built`, `done`, `parked`, `dropped: <reason>`, `blocked: <question for the user>`.

## Review findings

The review covered `hooks/`, `opencode/index.js`, the 34 skills, the docs and the evaluation code. `skills/verify/scripts/verify.py` (about 6,000 lines) was **not reviewed** and stays uncovered.

### Reproduced in this session

These were run against a scratch repository with `gate.analyse_command`:

| Command | Result |
|---|---|
| `python analysis/a.py` | classified, gated |
| `srun python analysis/a.py` | classified, gated |
| `mpirun -n 4 python analysis/a.py` | `[]`: not classified, so not gated |
| `torchrun analysis/a.py` | `[]` |
| `sudo -u bob python analysis/a.py` | `[]` |
| `python -c 'import analysis.a'` | `[]` |

So a covered script launched through `mpirun`, `torchrun` or `sudo -u`, or run by import, passes the gate unapproved. `WRAPPERS` in `hooks/shellwords.py:27` is a closed list, and an unknown launcher ends classification with no label.

Other checked facts:

- `hooks/tests/gate_diff_expected.json` holds counts, not cases: `cases: 173`, `fuzz: 120`, `seed: 1234`, `differences: 78`. It detects drift from base `267d9e2`; it cannot say whether a decision is right.
- The repository root has stray untracked files from a 2026-11-13 smoke run: `a/`, `run.sh`, `gate.json` (4 bytes, `x\nx\n`), `.a.scaffold.lock`. The live gate config is `.mycelium-extra/gate.json` (`{}`, valid), so the root `gate.json` is litter, not a broken config.
- `hooks/hooks.json` gives PreToolUse `timeout: 10`.

### Reported by review agents, not verified here

Hooks (`hooks/gate.py` unless named):

1. The approvals scan (`scan_seconds` up to 8, line 1064) and pin hashing (`pin_seconds` 5, line 54) run in sequence in `on_tool`. Their sum can pass the 10 s hook timeout, and a killed hook lets the call through.
2. A gate.json that fails to parse allows by default (`gate_run.py:155-157`), by design.
3. The freeze path (4078-4087) rewrites `pending/<session>.json` without the `state_lock` the stop path holds (4234).
4. The pin fallback records only size and `int(mtime)` (295-316), so a same-size edit in the same second passes.
5. `scan_approvals` (1084-1125) parses every approval file on every Bash call; the memo is per process.
6. `gate.py` is 4,993 lines; command parsing (409-1007) duplicates `shellwords.py` logic.

Skills and docs:

1. `verify`, at 250 lines, and `new-analysis`, at 156, break the 150-line hard limit in `skills/skill-style/SKILL.md:32`.
2. Nine skills have no `tests/` folder: `focus`, `handoff-resume`, `harden`, `idea-triage`, `plot-first`, `questionnaire`, `reflect`, `repo-setup`, `where`.
3. The `verify` description omits the `crate` subcommand; `knobs` has no SKILL.md section.
4. Several descriptions lack a "not for" line (`plot-first`, `diagnose-result`, `improve-structure`, `iterate`), which risks mis-routing against `mycelium:analyze` and `verify`.
5. Merge or demotion candidates (`handoff-resume` into `handoff`, `package-loop` into `iterate`, `focus` with `where`). Several conflict with recorded decisions: 0.33-0.36 shipped `iterate`, `package-loop` and `reflect` on purpose. They are listed for the user and not proposed here.

Evaluation:

1. No measure has produced a real result. Everything runs on synthetic fixtures, and no model run or human adjudication exists (`tests/eval/README.md:3`).
2. The 88 planted defects in `tests/e2e/defects.py` already pass (83 outside `known_miss`). They are saturated, so they serve as a guardrail and not as an objective.
3. The 14 eval scenarios need a paid model run and two adjudicators, under the caps in `docs/plans/2026-10-16-live-validation/`. Track R stays parked (`plans/_DONE/mycelium-extra-review-bundle/05_PARKED_AND_NON_GOALS.md:69-72`).

## Plan

The first benchmark is the gate's command classifier. `analyse_command` is pure apart from file stats, so it runs fast, needs no model, and gives labelled right or wrong answers. It also holds the most severe defect found.

| ID | Step | Choice | Source | Validation | Status |
|---|---|---|---|---|---|
| B0 | Remove the stray root files `a/`, `run.sh`, `gate.json`, `.a.scaffold.lock` | delete after the user confirms each | `user` | `git status --short` shows only `.claude/` | done |
| B1 | Build `tests/bench/gate_corpus/dev.jsonl` and `tests/bench/score_gate.py` | Each case: command, repo layout, expected `(label, paths)`. Mine `hooks/tests/test_gate.py` and the about 120 agent probes. Two error classes: false pass (covered script, `[]`) and false deny (benign command, gated) | see choices C1, C3 | scorer test on three hand cases; scorer reads no hook code except through `analyse_command` | built: 37 seeds, 567 mined |
| B2 | Seal a held-out corpus | A fresh agent writes `tests/bench/gate_corpus/heldout.jsonl` from the launcher and shell families only. The implementer never opens it; the scorer prints counts only | see choice C2 | file hash recorded in the benchmark card before B3 | built: sha256 6339a398… |
| B3 | Baseline on `789d7d6`; figure by `tests/bench/plot_gate_baseline.R` | Score dev and held-out separately, never pooled | `repo: tests/eval/README.md` (no pooling) | figure of false pass and false deny by command family, saved and inspected, cited by path | built: `tests/bench/results/789d7d6/` |
| B4 | Freeze the evaluator | Hash `tests/bench/` in an `iterate --mode method` card. Editable: `hooks/shellwords.py` and the parsing section of `hooks/gate.py` only | `repo: skills/iterate/references/method-mode.md:35-39` | loop guard blocks writes to hashed files | built: `tests/bench/card.md`; freeze runs when the tree starts |
| B5 | Guardrails for every candidate | full suite green; gate-diff with no unrecorded difference; defects 83/83 (latency: see C5) | see choice C5 | each candidate's ledger row records all four | todo |
| B6 | Fix rounds, ranked by what B3 fails | Each reviewer finding becomes a corpus case first; fixes go in a worktree, never the live checkout | `repo: HANDOFF.md` dead ends | dev and held-out counts per round | built: rounds 1-2 land as `0.36.2`; dev 0/37 false pass, 0/14 false deny; held-out 1/30 and 2/30, adjudication open |
| B7 | tusoskill run on B4's card | after B6 shows the loop works by hand | see choice C4 | tusoskill `stop-check` plus held-out score at the end only | todo |
| B8 | Fault-injection tests for findings 1, 3, 4 | timeout sum, freeze against stop, same-second pin | `default: they are not classification and need their own tests` | each test red on `789d7d6`, green after its fix | built: `hooks/tests/test_gate_faults.py`, lands as `0.36.3` |
| B9 | Second benchmark: skill text burden | description bytes, SKILL.md lines against the 150 limit, missing "not for" lines | `default: deterministic, already partly in tests/test_skill_frontmatter.py` | guardrail only, no tusoskill run | todo |

Seed cases for B1, from the hooks review, so B1 does not restart from the six reproduced above. False-pass seeds (a covered script behind each): `mpiexec`, `accelerate launch`, `flock`, `numactl`, `taskset`, `strace`, `perf`, `doas`, `runuser -u`, `su -c '…'`, `script -c '…'`, `systemd-run`, `git bisect run`, `git rebase -x '…'`, `builtin exec`, `pypy3`, `ipython`, `python -c 'from analysis import a'`, `runpy.run_path("analysis/"+"a.py")`. False-deny seeds: `python analysis/a.txt`, `python analysis/a.pyc`, `python analysis/`.

Held-out storage for B2: `heldout.jsonl` lives outside the repository tree, and the card records only its path and hash. Method mode blocks writes to hashed files but not reads, so a file inside the tree would be readable by the loop. Any read of it by the implementer or the loop turns it into dev, and a new held-out set is written (`tests/eval/README.md`, Development versus held-out).

One card: the `iterate --mode method` card in B4 is authoritative. tusoskill's benchmark card in B7 points at the same hashes and adds nothing of its own.

B8 findings as checked (2026-11-24). Finding 1 does not hold as written: in `on_tool` the hash budget starts before the approvals scan, so the two share one window and do not add. The real fault is that `pin_seconds` has no upper limit: at `pin_seconds: 30` a slow re-hash ran 20 s past a 10 s hook timeout in the test. A Bash call now stops re-hashing at 8 s (`TOOL_HASH_SECONDS`). A pin it could not re-hash compares by size and mtime and is named in the run notice and the launch record. Findings 3 and 4 held: the freeze now takes the stop path's lock, and pins record `mtime_ns`. Left open: `on_stop` can still sum several hash budgets past its 30 s timeout, but it writes `ready: False` first, so a kill there fails closed. Folder listings keep whole seconds, because switching them would mark every existing folder pin as changed.

Later, outside this plan: the 14 model-in-the-loop eval scenarios (blocked on cost approval and adjudicators); splitting `gate.py` (safer once B1 guards it); a review of `verify.py`; the skill merge list.

## Impactful choices for the user

Recommendations added 2026-11-24 at the user's request; all five approved the same day (Source `user`).

| ID | Recommended | Source |
|---|---|---|
| C1 | The pair (false passes, false denies), compared false passes first; no weighting, no composite | `repo: README.md` (an unapproved covered run is denied, so a false pass breaks the stated claim); `repo: tests/eval/README.md` ("There is no composite score") |
| C2 | Dev: every case mined from `hooks/tests/test_gate.py` (354 tests) plus the 28 seeds above. Held-out: 3 false-pass and 3 false-deny cases per command family, written by a fresh agent given only the family list | `default: coverage per family, no paper or count sizes it`; author rule from `repo: tests/eval/README.md` |
| C3 | Treat an unknown launcher as a gap when a later word resolves to a covered script, so it is denied; keep allowing it when no covered path follows | `repo: README.md` ("anything it could not check is shown as a gap, never as a pass"); `srun` already works this way (reproduced above) |
| C4 | 50 iterations, tusoskill's default | `package default: tusoskill SKILL.md, 50`; the held-out score at the end checks overfitting |
| C5 | Drop classifier latency as a guardrail; B8's whole-hook timeout test covers latency instead. Fuzz seed 1234 | Measured here: classifier median 0.09 ms, p95 0.16 ms, max 33 ms over 300 calls, against a 10 s hook timeout; seed `inherited: hooks/tests/gate_diff_expected.json` |

The questions:

| ID | Question | Why it matters |
|---|---|---|
| C1 | One scalar (for example false-pass count) or the pair (false pass, false deny) with a lexicographic order? Any weighting? | tusoskill needs one primary metric; the gate's own claim makes a false pass worse than a false deny |
| C2 | How many dev and held-out cases, and who writes held-out? | small held-out sets give noisy end scores; a held-out set the implementer saw becomes dev |
| C3 | An unknown launcher before a runner (`mpirun`, `torchrun`, `flock`): fail open (today) or fail closed? | this is a product decision; fail closed turns many benign HPC commands into denies |
| C4 | tusoskill iteration floor | tusoskill's SKILL.md sets 50 unless the user says otherwise, but `skills/iterate/references/method-mode.md:7` asks for the floor with no recommended value; this plan follows method-mode. A parser corpus may overfit dev long before 50 |
| C5 | Latency limit for the classifier, and the fuzz seed for any new fuzz cases | a slower classifier feeds finding 1; a seed has no default |

## Decisions to record

No `.living/` exists here, so the approved answers to C1-C5 are recorded in the recommendations table above and in `tests/bench/card.md`.

## Grill decisions (2026-11-24, user)

| Question | Answer |
|---|---|
| C3 reading | Narrow: a runner word or payload after an unknown program, plus a named list of direct launchers |
| Direct launchers | `valgrind`, `chrt`, `mpirun`, `mpiexec`, `horovodrun`, `strace`, `ltrace`, `perf`, `numactl`, `taskset`, `flock`, `sudo`, `doas`, `runuser`, `systemd-run`; the scan stops at the first reader |
| Option-value denies | Add `bat`, `pygmentize`, `highlight`, `shellcheck`, `source-highlight` to the reader list |
| Held-out adjudication | Once, after the last B6 round; then a fresh held-out set before B7 |
| Landing | Benchmark files first; the fix after round 2 |
| Version | `0.36.2` for the fix |
| B7 | Asked after round 2 is scored |
