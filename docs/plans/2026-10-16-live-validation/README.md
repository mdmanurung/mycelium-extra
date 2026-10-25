# Staged live validation packet

**Not approved.** This packet is reviewable preparation, not permission to send or submit. Cumulative external model/reviewer spend is EUR0 of EUR50. No broader release claim can be made while required checks remain unobserved.

## External review

Send the exact bytes of `review-prompt.txt` to Codex/OpenAI and Biomni/Phylo, once each, after explicit approval. The factual packet is identical (`review-packet.txt`). Current local Codex identity is recorded in `packet.json`; Biomni access/identity and provider cost bounds are unresolved release blockers. Do not substitute a reviewer/model or consume the EUR50 cap to probe access. The journey packet permits at most 64 model turns across both hosts, still within EUR20. Published [OpenAI model pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol) was checked on 2026-10-16: standard USD2/M input, USD0.10/M cached input, USD2.50/M cache writes, USD10/M output. At 6000 input tokens conservatively charged as cache writes plus 2000 total output/reasoning tokens, the arithmetic bound is USD0.035 per reviewer call before conversion, taxes, regional or tool fees. This is conditional on standard-tier API billing, not a confirmed charge for a subscription or a different tier. The EUR15 + EUR15 reviewer allocations and EUR20 agent-journey allocation are spending ceilings, not price estimates. Final approval requires verified estimates in the budget currency, any platform hard limits, and exact configured identities. Record cumulative actual cost, tokens, response IDs, timestamps and prompt/response hashes after each call; stop before any call whose maximum cost would exceed its allocation or EUR50 total.

Review independently, then have a human adjudicate each factual disagreement against the supplied packet. Retain both attributable responses, disagreements and disposition; a scripted user confirmation does not count as model judgment.

## Slurm packet

Read-only partition discovery on 2026-10-16 found `short` with a one-hour maximum. The proposed tasks each request one node, one CPU, no GPU, 1 GiB and five minutes. Four submissions produce five tasks: success, exit-7 failure, two array elements, and a cancellable sleep. No task is submitted by a test suite.

After approval, initialize the approval gate in a new disposable project, present the exact [scheduler plan](scheduler-plan.md) through the native host and obtain its same-session hash approval. Retain native PreToolUse/PostToolUse traces and plugin receipts, including unknown exit metadata. Copy the four reviewed scripts into that disposable working directory, record their SHA256s and the unique run directory, and submit each exactly once using `sbatch --parsable <script>`. Write a submission-intent record **before** every call. If interrupted before the job ID is recorded, query accounting for this exact run directory and script; unresolved identity forbids resubmission. Cancel only the exact job ID from this packet's cancel script after its started marker is observed. Inspect `sacct -j <id> --format=JobIDRaw,State,ExitCode,SubmitLine,WorkDir --parsable2`; retain per-array-element IDs, stdout/stderr, receipts and output hashes. Reconcile all five tasks, including cancellation, before marking A09 complete. Never relaunch a job during recovery.

## Native and behavioral qualification

Use disposable host configurations and an immutable candidate. Review and trust the exact current Codex hook definitions, record source/cache hashes and restart. Retain actual event traces plus terminal capture for denial/card/approval/run/failure/unknown/fresh-session reapproval and lifecycle/pause events. Mock API responses qualify only native control flow. Real responses and human adjudication are required for the journeys. Personal installations remain separate.

## Evaluation scaffold and native lifecycle journeys (C12)

Not run. [journeys.md](journeys.md) now also lists lifecycle journeys J15-J18 (approval, exploration, freeze, failure, recovery, verification) and host checks H01-H09 (effective cwd, raw tool aliases, `exec_command` workdir, missing call id, post failures, background jobs, unavailable hooks, hook errors, fresh-session reapproval), each marked NOT RUN with the approval or access it needs. Record the host's actual dispatch trace for each; a discovered skill or an invoked launcher does not count. The false-clean and burden scoring scaffold is in [tests/eval/](../../../tests/eval/README.md); it contains only synthetic examples and no results. These add no spend: EUR0 of EUR50 remains the cumulative total.

## Prereq review (2026-10-25, candidate 0.16.0)

Preparation only: nothing here approves a call or authorizes a job. This review requalifies the 2026-10-19 review, which was written against candidate 0.13.1, against 0.16.0 (`d810aaf`).

**Scheduler, re-checked against the cluster.** Partition `short` is `State=UP`, `MaxTime=01:00:00`, 39 nodes, `DefMemPerCPU=2048M`, so each script's one node, one CPU, 1 GiB and five minutes sits inside the partition's own limits; all four scripts pin `--partition=short` rather than relying on the default `all`, and `sinfo`, `sbatch`, `squeue` and `sacct` are present. The scripts still match the `scheduler` block in `packet.json`: `success.sh` prints and exits 0, `failure.sh` prints and exits 7, `array.sh` declares `--array=0-1` (two elements), `cancel.sh` prints a started marker and then sleeps 60 seconds. Four submissions therefore produce the five task outcomes that `scheduler-plan.md` S5 requires.

**Journeys, re-checked against the candidate.** J01-J14 name only skills that exist in the candidate (13 skills, all present); J12 and J13 are Mycelium-core and native-host journeys, deliberately not mycelium-extra skills. J15-J18 and H01-H09 remain NOT RUN. One enumeration had gone stale at 0.13.1: J07 asked for eight actions while the candidate offered ten. It now says "every action the installed skill lists, including runs and refs", and the expected-behavior cell names the ten earlier actions plus `report --trace`, `exercise` and `exercise reveal`. `grill` gained `explain plan` and track-changes gained a read-only Plan tab; neither adds a skill or a gated action J01-J14 must call.

**Frozen bytes.** `packet.json` records the SHA256 of every file it lists, nine files, and `manifest_sha256` hashes the sorted `name:hash` lines. The nine digests and the manifest were recomputed on 2026-10-25 for candidate 0.16.0. `README.md` and `journeys.md` changed; `scheduler-plan.md`, `review-packet.txt`, `review-prompt.txt` and the four scripts are byte-identical and keep their recorded digests.

**Still unresolved, and only the user can close it:** Biomni/Phylo access and its configured identity, the EUR billing bounds and exact identities for both reviewers, and the Claude model identity and rate for the journey turns. `status` remains `NOT APPROVED`.
