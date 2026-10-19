# Plan: unblock the remaining blockers (2026-10-18)

Companion to `HANDOFF.md` (the resume file) and `docs/roadmap/08-working-scope.md` (the 0.11.0 tracker). This document turns the open items in those files into a sequenced, owned plan. Items already closed this cycle are listed at the end for context; nothing here re-opens them.

Status key: **me** = agent can execute now; **you** = needs your decision/approval; **env** = needs tooling or access not present; **time** = cannot be done before its date.

## Summary

| # | Blocker | Owner | Status |
|---|---|---|---|
| B1 | `docs/example.md` still says 0.10.2 | env (+ me) | **Closed 2026-10-19.** Regenerated at 0.12.0 (`316b7af`) — both tools exist after all, see below |
| B2 | C12 evaluation (H01–H09, J15–J18, C11 reviewers) | you | Open: packet frozen and reviewed, but approval and the provider identities are still yours |
| B3 | Plan A (CT-1/DT-1/VR-1/D2/D3/ER-1/ED-1) | you → me | **Closed 2026-10-19** for CT-1/DT-1/VR-1/ER-1; D2/D3 to the mindfulness bundle; ED-1 deferred |
| B4 | ~2026-10-31 measurement | time (+ me) | **Closed 2026-10-19** as prep: spec in `docs/development.md` and a dated baseline taken |
| B5 | OpenCode synthetic stop messages reach the model | env (real host) | **Unit-test half closed 2026-10-19**; the host half stays with C12 (H07/H08) |
| B6 | 0.11.0 tag | you | Your call |
| B7 | M5 "update memory" note | you (global memory) | No `.living/` in this repo |
| B8 | bmv unreceipted run (2026-10-17 12:35–12:44) | — | Asked once, you don't remember; do not ask again |
| B9 | Native host checks / human adjudication | you | Part of C12 |
| B10 | C12 packet not frozen (README.md, journeys.md drifted from recorded hashes) | me (prep) / you (approval) | **Closed 2026-10-19.** All nine listed files match; prereq review recorded; `status` still `NOT APPROVED` |

## B1 — `docs/example.md` still says 0.10.2

- **State.** The header reads "at version 0.10.2" on a run dated 2026-10-17. The handoff says its output blocks did not change under 0.11.0.
- **Reality check.** `tests/test_example.py` only checks that quoted status lines and commands still exist in the sources, that the README links it, and that no scratch paths leak. It does **not** assert the version number. So the version stamp is documentation, not a tested contract.
- **Why it is blocked.** Regeneration needs a real `scilintr` (Python linter) and an `Rscript` whose R has `scilintr`. `scilintr` is not on PyPI; the only copy found is an R package at `/exports/para-lipg-hpc/mdmanurung/R/4.5/scilintr`, and no R 4.5 binary is on `PATH` (only R 4.1 via the `rnotebook` conda env, which does not have `scilintr`). `make_example.py` exits unless both tools exist.
- **Assessment.** The file is a **dated record of a real run**, not a live spec. The 0.11.0 changes (re-pin notices, amendment cards, freeze) are additive gate behaviors that the example's run never exercises, so the handoff's "output blocks did not change" holds. The 0.10.2 stamp was accurate as history, not stale.
- **Closed 2026-10-19 — it was regenerable after all.** The tools the earlier search missed: the Python `scilintr` is in the archive conda env `/exports/archive/hg-funcgenom-research/mdmanurung/conda/envs/codex/bin/scilintr` (site-packages under `python3.14`), and R 4.5.3 with the `scilintr` R package is `/exports/para-lipg-hpc/mdmanurung/conda/envs/cellbouncer/bin/Rscript` with `R_LIBS_USER=/exports/para-lipg-hpc/mdmanurung/R/4.5` (`requireNamespace("scilintr")` → TRUE). `MX_E2E_SCILINTR=... MX_E2E_RSCRIPT=... python3.12 tests/e2e/make_example.py` regenerated the page at 0.12.0 (`316b7af`); the diff is the date, the version and the instance ids, nothing else, and `tests/test_example.py` passes (4 tests). The 0.11.0 "output blocks did not change" expectation is now recorded in the file itself rather than assumed.

## B2 — C12 evaluation (H01–H09, J15–J18, external reviewers)

- **State.** `docs/plans/2026-10-16-live-validation/` is marked "NOT APPROVED - do not execute external calls or submit jobs". Budget EUR50, EUR0 spent. Biomni/Phylo identity is unresolved; EUR billing conversion/taxes unresolved; Slurm partition `short` (1 h max) discovered but no job submitted; native host checks H01–H09 and lifecycle journeys J15–J18 NOT RUN. C11 external reviewer calls never made.
- **What I did this session (prereq review, no execution).** Verified the packet's file hashes: 7 of the 9 listed files matched (`scheduler-plan.md`, `review-packet.txt`, `review-prompt.txt`, `cancel.sh`, `success.sh`, `failure.sh`, `array.sh`). `README.md` and `journeys.md` **mismatched** — they drifted after the packet was hashed (the J15–J18 and H01–H09 additions). Earlier notes said "6 of 8", counting the packet itself and one file short. So the packet was not in a frozen, approval-ready state.
- **Done 2026-10-19 (still no execution).** The prereq review below was completed and recorded in `docs/plans/2026-10-16-live-validation/README.md` ("Prereq review"), and `packet.json` now records the SHA256 of all nine files: 9 of 9 match, `status` unchanged at `NOT APPROVED`. The review re-checked partition `short` (`State=UP`, `MaxTime=01:00:00`, 39 nodes, `DefMemPerCPU=2048M`) against the four scripts, found one stale enumeration in J07 (eight actions; the candidate offers ten plus `report --trace`) and fixed it, and confirmed J01–J14 name only skills that exist in the candidate.
- **Unblock path (yours).**
  1. ~~Freeze the packet~~ **Done 2026-10-19**: all nine files match their recorded digests (`status` still `NOT APPROVED`).
  2. Resolve Biomni/Phylo identity and verified EUR billing bounds (provider-side; nothing I can do).
  3. Approve the packet (flip `status` to approved). Then: send `review-prompt.txt` bytes to Codex/OpenAI and Biomni/Phylo once each (≤64 turns, EUR20 journey cap, EUR15+EUR15 reviewer caps), run the Slurm scripts (`success.sh`, `failure.sh`, `array.sh`, `cancel.sh`) per `scheduler-plan.md`, and run H01–H09 and J15–J18 in disposable host configs with real event traces.
  4. Human adjudication of every factual disagreement; retain both responses, disagreements and disposition.
- **Prereq review: done 2026-10-19.** `journeys.md` was read in full, `scheduler-plan.md` was verified against the cluster, and the four script digests still match the packet. The findings and the re-freeze are recorded in `docs/plans/2026-10-16-live-validation/README.md`. Nothing about this consumed spend or submitted a job.

## B3 — Plan A (mycelium_grill roadmap specification)

- **State (2026-10-18).** NOT started: no code, no tracker; IDs absent outside `plans/`; D2/D3 still `todo` at `docs/roadmap/05-mindfulness-core.md:33,46`.
- **Closed 2026-10-19 as scoped and executed.** The specification was audited against the code and turned into the tracker `docs/roadmap/11-coverage-and-evidence.md`: CT-1 (`86ffafa`), DT-1 (`8884233`), VR-1 (`3df29df`) and ER-1 (`9d136c5`) are done with test evidence, and the tracker's own audit table records what the specification had got wrong (it was written against 0.10.2). D2/D3 are carried by the mindfulness bundle rather than here, and ED-1 stays deferred.

## B4 — Measurement (~2026-10-31)

- **State.** By design future; the review date is fixed and the sources already exist.
- **Closed 2026-10-19 as preparation.** The collection spec is in `docs/development.md` ("Usage measurement (the ~2026-10-31 review)"): read-only `jq`/`wc` checks for approvals per day and latency (`approvals.jsonl`; the folder count is the independent second count because the log only starts at 0.11.0), denials and reasons (`denies.jsonl`), re-pins (`repins/*.jsonl`), launches and explore grants, gate errors (`gate-errors.jsonl`) and `provenance/` folders. Every command was run against both live projects before being written down. Two things it explicitly cannot measure are stated there: `verify` reads leave no record at all (only `verify write` leaves a `provenance/` folder), and `card_coverage` use is not recorded anywhere.
- **Baseline captured.** There was no pre-0.11.0 baseline, so the dated first reading in that section (2026-10-19) is the "before": `bmv_pilot_cytof_integration` 99 approvals in the folder, 379 receipts, 21 gate errors (20 of them a Python 3.6 hook host), 42 `provenance/` folders; `scale` 45 approvals, 196 receipts, 3 `provenance/` folders and no logs at all.
- **Remaining.** Wait for 2026-10-31, run the same block, and compare.

## B5 — OpenCode synthetic stop messages reaching the model

- **State.** The adapter delivers notices via `ctx.session.synthetic({ sessionID, text: notice })` (`opencode/index.js`) when a notice string exists and `ctx.session.synthetic` is a function, and `ctx.session.prompt({ delivery: "steer" })` when the Stop hook blocks; `hooks/gate.py` `lint_stop_block` produces the blocking reason and `new_explore_runs`/`open_lint_notice` produce the notices.
- **Closed 2026-10-19 for the unit-test half.** Two tests now in `opencode/tests/gate.test.js` (12 → 14 tests, all passing):
  1. a Stop notice (a recorded exploratory run for the session) reaches the model as `session.synthetic`, with the delivered text asserted *equal to the gate's own `systemMessage`* from an identical fixture — and `session.prompt` stays empty, so a notice is never delivered as a steering prompt;
  2. a blocking Stop (`lint_before_stop: true` with a planted open finding in the gate's own lint state) is delivered as `session.prompt` with `delivery: "steer"` and the reason text — and `session.synthetic` stays empty. The earlier note in this file said the lint-stop reason would go out as a synthetic message; it does not, it steers.
  Both tests were mutation-checked: removing the synthetic call fails the first, removing `lint_before_stop` fails the second.
- **Still open (host half).** Whether the host surfaces that text in the model's context is a real-host question, not a unit-test question. It stays with C12's host checks (H07/H08); folding it there avoids a separate model spend.

## B6 — 0.11.0 tag

- **State.** Pushed untagged (`4ac6726`); `CHANGELOG.md:5` and the four manifests agree on 0.11.0.
- **Unblock path.** `git tag v0.11.0 && git push origin v0.11.0` (or an annotated tag). This is your call and your push; I will not tag without explicit go-ahead. If you want it, say the word and I run both commands.

## B7 — M5 "update memory" note

- **State.** `docs/roadmap/08-working-scope.md` M5 lists "Update memory (`human-in-the-loop-priority` is reversed; `researcher-first-redesign` status)." This repository has no `.living/`, so the note refers to your global memory, not repo state.
- **Unblock path.** Yours: update the global memory entry. Nothing for me to do in this repo.

## B8 — bmv unreceipted run (2026-10-17 12:35–12:44)

- **State.** Asked once (2026-10-18); you do not remember. Checked: no `.mycelium-extra` gate state exists in `bmv` today; the sessions `9e6bf4bd`/`3d3963d2` are not in the OpenCode store under those ids; no receipt exists either way.
- **Unblock path.** None available — the evidence is gone. Recorded as asked-and-unanswered; do not ask again. Treat any result from that window as unverified and do not quote it.

## B9 — Native host checks and human adjudication

- **State.** Part of C12 (H01–H09, J15–J18). Needs disposable host configs, real sessions, human-marked criteria.
- **Unblock path.** Same as B2: packet approval first. No code work until then.

## B10 — C12 packet not frozen

- **State (2026-10-18).** 7 of the 9 listed files matched their recorded SHA256; `README.md` and `journeys.md` mismatched (they grew the J15–J18 and H01–H09 sections after hashing).
- **Closed 2026-10-19.** The prereq review was completed first — partition `short` re-checked against the cluster, the four scripts read against the `scheduler` block, `journeys.md` read in full against the candidate — then `packet.json` was re-hashed so all nine files match, and the review is recorded as the "Prereq review" section of the packet's `README.md`. `status` stays `NOT APPROVED - do not execute external calls or submit jobs`; approval remains yours, and freezing the bytes is what makes that approval verifiable.

## What I can do now (no approval, no spend)

1. ~~**C12 prereq review**~~ — **done 2026-10-19**: `journeys.md` read in full, `scheduler-plan.md` verified against the cluster, the four script digests confirmed, gaps reported. (B2, B9, B10)
2. ~~**OpenCode synthetic test**~~ — **done 2026-10-19**: two tests in `opencode/tests/gate.test.js`, mutation-checked. (B5)
3. ~~**Measurement collection spec**~~ — **done 2026-10-19**: the "Usage measurement" section of `docs/development.md`, with a dated baseline. (B4)
4. ~~**Reclassify `docs/example.md`**~~ — **done 2026-10-19**: regenerated at 0.12.0, so it is neither stale nor merely historical. (B1)

## What only you can do

- Approve/decline the C12 packet (B2, B9) and resolve Biomni/Phylo identity + EUR billing bounds.
- Tag `v0.11.0` (B6).
- Update your global memory (B7).

## Recommended order

1. You: approve or decline the C12 packet (unblocks B2, B9 and B5's host half).
2. 2026-10-31: run the measurement (B4).

## Closed this cycle (for context)

A-3 guard text, CI base pin, `tests/test_ci_pins.py`, the `gate-diff` on-demand trigger, the interpreter-portable oracle (`VolatileTextTest`), the 3.11 `LC_ALL=C` leg, the bmv question (asked once, unanswered), and the C12 packet hash check. All pushed to origin (`4ac6726`); CI green on the last commit.

Also closed on 2026-10-19: **B1** (`docs/example.md` regenerated at 0.12.0, `316b7af`), **B3** (the mycelium_grill specification audited into `docs/roadmap/11-coverage-and-evidence.md` and its CT-1/DT-1/VR-1/ER-1 milestones shipped), **B4** (measurement spec plus a dated baseline in `docs/development.md`), **B5** (the two OpenCode Stop-delivery tests) and **B10** (the C12 packet re-frozen, 9 of 9 digests, prereq review recorded).