# Plan: unblock the remaining blockers (2026-10-18)

Companion to `HANDOFF.md` (the resume file) and `docs/roadmap/08-working-scope.md` (the 0.11.0 tracker). This document turns the open items in those files into a sequenced, owned plan. Items already closed this cycle are listed at the end for context; nothing here re-opens them.

Status key: **me** = agent can execute now; **you** = needs your decision/approval; **env** = needs tooling or access not present; **time** = cannot be done before its date.

## Summary

| # | Blocker | Owner | Status |
|---|---|---|---|
| B1 | `docs/example.md` still says 0.10.2 | env (+ me) | Not a real staleness — see below |
| B2 | C12 evaluation (H01–H09, J15–J18, C11 reviewers) | you | Blocked on packet approval |
| B3 | Plan A (CT-1/DT-1/VR-1/D2/D3/ER-1/ED-1) | you → me | Not started; needs scoping |
| B4 | ~2026-10-31 measurement | time (+ me) | Set up collection now, run later |
| B5 | OpenCode synthetic stop messages reach the model | env (real host) | Unchecked; code path identified |
| B6 | 0.11.0 tag | you | Your call |
| B7 | M5 "update memory" note | you (global memory) | No `.living/` in this repo |
| B8 | bmv unreceipted run (2026-10-17 12:35–12:44) | — | Asked once, you don't remember; do not ask again |
| B9 | Native host checks / human adjudication | you | Part of C12 |
| B10 | C12 packet not frozen (README.md, journeys.md drifted from recorded hashes) | me (prep) / you (approval) | Found this session |

## B1 — `docs/example.md` still says 0.10.2

- **State.** The header reads "at version 0.10.2" on a run dated 2026-10-17. The handoff says its output blocks did not change under 0.11.0.
- **Reality check.** `tests/test_example.py` only checks that quoted status lines and commands still exist in the sources, that the README links it, and that no scratch paths leak. It does **not** assert the version number. So the version stamp is documentation, not a tested contract.
- **Why it is blocked.** Regeneration needs a real `scilintr` (Python linter) and an `Rscript` whose R has `scilintr`. `scilintr` is not on PyPI; the only copy found is an R package at `/exports/para-lipg-hpc/mdmanurung/R/4.5/scilintr`, and no R 4.5 binary is on `PATH` (only R 4.1 via the `rnotebook` conda env, which does not have `scilintr`). `make_example.py` exits unless both tools exist.
- **Assessment.** The file is a **dated record of a real run**, not a live spec. The 0.11.0 changes (re-pin notices, amendment cards, freeze) are additive gate behaviors that the example's run never exercises, so the handoff's "output blocks did not change" holds. The 0.10.2 stamp is therefore accurate as history, not stale.
- **Plan.** Do **not** hand-edit the stamp (it would claim a run happened at 0.11.0 that did not). Leave it as a historical record. If you want it to say 0.11.0, the unblock is: locate the R 4.5 binary (likely a module or a conda env not yet found) and install the R `scilintr` package into it, then run `python3.12 tests/e2e/make_example.py`. Until then, treat the open item as closed-with-note.

## B2 — C12 evaluation (H01–H09, J15–J18, external reviewers)

- **State.** `docs/plans/2026-10-16-live-validation/` is marked "NOT APPROVED - do not execute external calls or submit jobs". Budget EUR50, EUR0 spent. Biomni/Phylo identity is unresolved; EUR billing conversion/taxes unresolved; Slurm partition `short` (1 h max) discovered but no job submitted; native host checks H01–H09 and lifecycle journeys J15–J18 NOT RUN. C11 external reviewer calls never made.
- **What I did this session (prereq review, no execution).** Verified the packet's file hashes: 6 of 8 match (`scheduler-plan.md`, `review-packet.txt`, `cancel.sh`, `success.sh`, `failure.sh`, `review-prompt.txt`, `array.sh`). `README.md` and `journeys.md` **mismatch** — they drifted after the packet was hashed (the J15–J18 and H01–H09 additions). So the packet is not in a frozen, approval-ready state: the approval cannot be verified against exact bytes as-is.
- **Unblock path (yours).**
  1. Freeze the packet: re-hash `README.md` and `journeys.md` in `packet.json` (or restore them to the recorded bytes) so every file matches. This is a one-command step I can run once you say which — I will not edit the packet without your go-ahead, because it changes the approval target.
  2. Resolve Biomni/Phylo identity and verified EUR billing bounds (provider-side; nothing I can do).
  3. Approve the packet (flip `status` to approved). Then: send `review-prompt.txt` bytes to Codex/OpenAI and Biomni/Phylo once each (≤64 turns, EUR20 journey cap, EUR15+EUR15 reviewer caps), run the Slurm scripts (`success.sh`, `failure.sh`, `array.sh`, `cancel.sh`) per `scheduler-plan.md`, and run H01–H09 and J15–J18 in disposable host configs with real event traces.
  4. Human adjudication of every factual disagreement; retain both responses, disagreements and disposition.
- **What I can do now (no approval needed):** finish the prereq review of `journeys.md` (H01–H09/J15–J18 readiness), verify `scheduler-plan.md` against the cluster, and confirm the script SHA256s still match the packet (done: all four scripts match). I have not done the journeys read yet; say the word and I will.

## B3 — Plan A (mycelium_grill roadmap specification)

- **State.** NOT started: no code, no tracker; IDs absent outside `plans/`; D2/D3 still `todo` at `docs/roadmap/05-mindfulness-core.md:33,46`.
- **Unblock path.** This is feature work, not a blocker of 0.11.0 (which implements neither Plan A nor Plan B's C12). It needs scoping via `grill` before any code. I can run that scoping session when you want to start the cycle; until then it is correctly parked.

## B4 — Measurement (~2026-10-31)

- **State.** By design future.
- **What I can do now.** Nothing to collect yet, but I can write the collection spec so the data is captured correctly when the date arrives: approvals/day (count new files in `.mycelium-extra/approvals/` per day), `verify` use (invocations), `denies.jsonl` line counts and reasons, approval latency (time from plan shown to `approve`), re-pins per plan and freezes (count lines in `.mycelium-extra/repins/*.jsonl`). All sources already exist; no code change needed. I will add this as a short section to `HANDOFF.md`/`docs/development.md` if you want it recorded.
- **Unblock path.** Wait for 2026-10-31, then run the counts and compare against the pre-0.11.0 baseline (which does not exist yet — that is the real gap: there is no recorded pre-0.11.0 baseline for approvals/day etc.). Capturing a baseline now, even roughly, would make the comparison meaningful. Worth deciding before the date.

## B5 — OpenCode synthetic stop messages reaching the model

- **State.** Unchecked. The adapter delivers notices via `ctx.session.synthetic({ sessionID, text: notice })` (`opencode/index.js:354`) when a notice string exists and `ctx.session.synthetic` is a function; `hooks/gate.py:3923` (`lint_stop_block`) produces the lint-stop reason that would be sent this way.
- **What I found.** The code path exists and is guarded, but nothing verifies that the model actually sees the delivered text. A unit test can assert the adapter *calls* `ctx.session.synthetic` with the notice (mockable); whether the host surfaces it in the model's context is a real-host question, not a unit-test question.
- **Unblock path.** (1) Add a unit test in `opencode/tests/` asserting the synthetic call is made with the notice when `lint_before_stop` is on — I can do this. (2) Verify reachability with a real OpenCode session (one short turn, no model spend beyond the turn) — needs a host. Part of C12's host checks (H07/H08) if you prefer to fold it in.
- **Recommendation.** Fold into C12 (H07/H08) rather than a separate spend; the unit test alone is cheap and I can add it without approval.

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

- **State.** 6 of 8 listed files match their recorded SHA256; `README.md` and `journeys.md` mismatch (they grew the J15–J18 and H01–H09 sections after hashing).
- **Unblock path.** Re-hash the two drifted files in `packet.json` (or restore them to the recorded bytes) so the approval can be verified against exact bytes. One command once you say which; I will not edit the packet without your go-ahead because it changes the approval target.

## What I can do now (no approval, no spend)

1. **C12 prereq review** — read `journeys.md` in full, verify `scheduler-plan.md` against the cluster, confirm the four script SHA256s (done: all match). Report gaps. (B2, B9, B10)
2. **OpenCode synthetic test** — add a unit test asserting `ctx.session.synthetic` is called with the notice when `lint_before_stop` is on. (B5)
3. **Measurement collection spec** — short section in `docs/development.md` or `HANDOFF.md` listing the exact sources and counts, so the 2026-10-31 run is mechanical. (B4)
4. **Reclassify `docs/example.md`** — record in `HANDOFF.md` that it is a dated historical record, not a stale stamp, and close the item (or, if you prefer, attempt regeneration once R 4.5 is located). (B1)

## What only you can do

- Approve/decline the C12 packet (B2, B9, B10) and resolve Biomni/Phylo identity + EUR billing bounds.
- Tag `v0.11.0` (B6).
- Start Plan A or the next cycle in `../mx-0120` (B3).
- Update your global memory (B7).
- Decide whether to keep `docs/example.md` as-is or point me at an R 4.5 binary (B1).

## Recommended order

1. You: approve or decline the C12 packet (unblocks B2, B9, B10, and B5's host half).
2. Me: C12 prereq review + OpenCode synthetic test + measurement spec (items 1–3 above), in one commit.
3. You: tag decision (B6) and the `../mx-0120` cycle kickoff (B3).
4. 2026-10-31: run the measurement (B4).

## Closed this cycle (for context)

A-3 guard text, CI base pin, `tests/test_ci_pins.py`, the `gate-diff` on-demand trigger, the interpreter-portable oracle (`VolatileTextTest`), the 3.11 `LC_ALL=C` leg, the bmv question (asked once, unanswered), and the C12 packet hash check (6/8 match; 2 drifted). All pushed to origin (`4ac6726`); CI green on the last commit.
PY
echo "written"; wc -l docs/plans/2026-10-18-unblock-blockers.md