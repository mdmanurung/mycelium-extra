# Mindfulness core

[Back to roadmap](README.md)

Tasks that keep the researcher, not the agent, responsible for what an analysis claims. The existing tools check that the right code ran on the right data. These check that what is written about the results matches what the results are, and that the researcher knows which parts they established themselves.

Two documents from the planning session feed D1: `claim_artifact_checker_design.md` (design) and `SKILL_verify_claims.md` (draft skill text). Commit them under `docs/design/` when D1 starts, so the grill prompt can cite them.

### D1: Claim-versus-artifact checker

- **Why:** an agent can write "312 genes were differentially expressed (FDR < 0.05)" when the results table has 287 rows passing that threshold, or cite a figure that a later run overwrote. Verify checks that the planned code ran; nothing checks that the numbers in the prose match the outputs. This is the most common way LLM-written analysis text goes wrong without anyone noticing.
- **Scope:** as in the design document: EXTRACT numeric claims from a findings file or report (from an authored claims block where present, else conservative patterns), LOCATE the artifact each claim cites, MATCH the value with a stated tolerance and transform (count, proportion, rounding). Verdicts `VERIFIED`, `verified-transform`, `MISMATCH`, `UNVERIFIED`, `EXCLUDED`, `verified-explore-only`, under schema `mycelium-extra.claims.v1`. A common-value guard so that a claim of "3" is not matched to any 3 in a large table. The report ends with `Claims: PASS`, `Claims: PASS_WITH_GAPS (N)`, or `Claims: FAIL (...)`.
- **Out of scope:** checking qualitative claims ("strongly enriched"); any LLM call in extraction or matching; editing the prose.
- **Depends on:** C1 (fixture findings with planted mismatches).
- **Constraints:** stdlib only, Python 3.6. An unlocated artifact is `UNVERIFIED` (a gap), never `VERIFIED`. A claim matched only to an explore output is `verified-explore-only` and cannot make the status PASS, since explore outputs are never promoted to results. Decide in grill whether this is a standalone `verify-claims` skill or a `claims` mode of verify; the draft leaves it open.
- **Grill prompt:** `/mycelium-extra:grill Build the claim-versus-artifact checker described in docs/design/claim_artifact_checker_design.md, using docs/design/SKILL_verify_claims.md as the draft skill. First decide whether it is a standalone skill or a verify mode, citing how verify already reports gaps. Then plan extraction, location, and matching with the common-value guard, using the fixture project's planted mismatches as the acceptance set.`
- **Acceptance:** on the fixture, every planted mismatch is `MISMATCH`, every correct claim is `VERIFIED` or `verified-transform`, a claim citing a missing file is `UNVERIFIED`, and the status line matches.
- **Tests:** unit tests per verdict; a false-match test for the common-value guard; an end-to-end case in `tests/test_end_to_end.py`.
- **Effort:** L.
- **Status:** done in 0.9.34, as a verify stage, not a skill. Its grill chose an authored claims block whose lines name their cell (`value | file column [row]`) over prose extraction with context scoring, which could not catch the fixture's planted mutation without tuning; numbers outside the block are listed as info. Parked: prose scoring, log2 and -log10 transforms, Markdown table diffs, text and log artifacts, a `claims_report.json`, and a mode with no plan. See the note at the top of [the design](../design/claim_artifact_checker_design.md).

### D2: Citation resolution

- **Why:** LLMs produce plausible references that do not exist, or real references attached to claims they do not support. A methods section that cites a non-existent paper for a normalization choice is a reportable error.
- **Scope:** for each DOI, PMID, or arXiv ID in a findings file or report, check that it resolves (Crossref, NCBI E-utilities, arXiv) and that the returned title and first author match the citation text; report `resolved`, `mismatch`, `unresolved`, or `not checked (offline)`. Optionally, when the user asks, show the abstract next to the sentence that cites it so the user can judge support.
- **Out of scope:** judging whether a paper supports the claim (the user does that); full-text retrieval; references without an identifier, which are listed as `no identifier`.
- **Depends on:** D1 (shares the extraction step and report format).
- **Constraints:** network access is opt-in per run and stated before any request; offline is a gap, not a pass. stdlib `urllib` only. Rate-limit requests and send a contact address only if the user configures one.
- **Grill prompt:** `/mycelium-extra:grill Add citation resolution to the claims checker: resolve each DOI, PMID, or arXiv ID and compare title and first author with the citation text. Plan the opt-in network step, the offline gap, and how results join the claims report.`
- **Acceptance:** a fixture report with one real, one fabricated, and one mismatched citation gives `resolved`, `unresolved`, and `mismatch`; with network disabled all three are `not checked (offline)` and the status is not PASS.
- **Tests:** unit tests with recorded API responses (no live network in tests).
- **Effort:** M.
- **Status:** todo.

### D3: Disclosure skill

- **Why:** journals and funders increasingly ask how AI tools were used. The receipts already record which steps an agent planned, ran, and which the user approved, but writing that up is left to memory, which tends to understate the agent's role.
- **Scope:** a `disclose` skill that reads the receipts, approvals, verify status, and (when D1 exists) claims status for one analysis folder and drafts a short methods paragraph: which tools and versions, what the agent did, what the user reviewed and approved, which checks ran and what they found. The user edits it; the skill never writes it into a manuscript.
- **Out of scope:** journal-specific templates; judging whether the use was appropriate.
- **Depends on:** D1 (claims status); A3 (version numbers the paragraph can cite).
- **Constraints:** every sentence in the draft must trace to a record; anything the records cannot show is left as a marked blank for the user, not filled in. Plain text output.
- **Grill prompt:** `/mycelium-extra:grill Plan a disclose skill that drafts an AI-use methods paragraph for one analysis folder from its receipts, approvals, verify status, and claims status. Each sentence must cite the record it comes from; gaps stay as marked blanks.`
- **Acceptance:** on the fixture, every sentence in the draft maps to a record; removing the receipts turns the matching sentences into blanks.
- **Tests:** contract test that each sentence carries a source tag; unit test for the blank-on-missing rule.
- **Effort:** M.
- **Status:** todo.

### D4: Multiplicity view in verify

- **Why:** an agent can run many tests, models, or thresholds and report the one that worked. Receipts record every run, so the number of analyses attempted per reported result is knowable, but nobody shows it. This is the guard named for the "silent forking paths" failure mode.
- **Scope:** `verify multiplicity` lists, per plan, how many runs touched the same outputs or the same contrast, how many plan revisions changed a threshold or model, and how many explore runs preceded the approved run. Read-only; no judgement, just counts and the run list.
- **Out of scope:** correcting p-values; deciding which run is the "real" one.
- **Depends on:** C1.
- **Constraints:** explore runs are counted but never promoted; counts come only from receipts and approvals, and a missing record is a gap.
- **Grill prompt:** `/mycelium-extra:grill Add a read-only multiplicity view to verify: per plan, count runs on the same outputs, plan revisions that changed thresholds or models, and explore runs before the approved run. Read how receipts and approvals link runs to plans, and plan the output table.`
- **Acceptance:** on a fixture with three explore runs and two plan revisions before the approved run, the view shows those counts and lists the runs.
- **Tests:** unit tests on synthetic receipts; an end-to-end case.
- **Effort:** M.
- **Status:** done (0.9.36). `verify multiplicity <hash>` shows a counts line and one timeline: earlier approved plans that share a script or output, with their changed Choice cells, then explore runs, runs under earlier plans, and this plan's runs, up to its last run. Plans are content hashes with no link to the plan they replace, so overlap of scripts or outputs is the link. Parked: a multiplicity section in `PROVENANCE.md` (when D3 needs it), a git diff of the code versions, and counting per contrast.

### D5: LLM failure-mode checklist in grill

- **Why:** grill's analysis-decisions list covers what a careful analyst would decide. It does not cover the ways an LLM agent specifically goes wrong (inventing a column, swapping a contrast, wrapping a failure in `|| true`, claiming a check ran).
- **Scope:** `skills/grill/references/llm-failure-modes.md` with a guard-per-mode rule linked from grill's SKILL.md, two scenarios in `scenarios.md`, and a contract test.
- **Out of scope:** new checks; the `planned:` entries point to D1, D2, and D4.
- **Depends on:** none.
- **Constraints:** every `cross-ref:` names an existing analysis-decisions row; every `planned:` names a task in this roadmap.
- **Grill prompt:** not needed; delivered with this roadmap.
- **Acceptance:** `python3 skills/grill/tests/test_grill_references.py` passes.
- **Tests:** `skills/grill/tests/test_grill_references.py`.
- **Effort:** S.
- **Status:** done.

### D6: h5ad support and graded batch imbalance in data-contract-check

- **Why:** data-contract-check v1 reads CSV/TSV only, so single-cell projects, where the sample table usually lives in an `.h5ad` file's `obs`, get no check. Its `batch_confounding` check already blocks a contrast fully nested in batch or a level that shares no batch with another, and warns when a batch holds one level or a level sits in one batch. What it does not report is graded imbalance, such as one batch holding 80% of one condition, and it prints the batch-by-condition table only as evidence for a failure.
- **Scope:** read `obs` (and `uns` keys if needed) from `.h5ad` through `h5py` when it is installed, else report a gap; extend `batch_confounding` with an optional `max_share` field that warns when any batch holds more than that share of one contrast level, and print the cross-table on every run of the check.
- **Out of scope:** reading `X` or layers; `.rds`/Seurat objects (a later task if wanted); changing what the check already blocks.
- **Depends on:** none.
- **Constraints:** `h5py` is optional, never required; without it the check is a gap. `max_share` is a contract field the plan sets, with its reason, so the plan owns the number; without it the check behaves as today.
- **Grill prompt:** `/mycelium-extra:grill Extend data-contract-check to read obs from h5ad files when h5py is available, and add an optional max_share imbalance warning to the existing batch_confounding check. Read check_batch first and keep everything it blocks and warns on today unchanged.`
- **Acceptance:** on a fixture `.h5ad` the existing checks run unchanged; with `max_share: 0.7` and one batch holding 80% of one level, the check warns and shows the table; without `h5py` the check reports a gap (status `GAP`, exit 3; a gap never passes). An unreadable column or unrecognised `obs` encoding is also a gap, for the checks that name it.
- **Tests:** unit tests with a tiny generated `.h5ad` (skipped when `h5py` is missing) and CSV equivalents for the imbalance logic; the existing tests pass unchanged.
- **Effort:** M.
- **Status:** done.

### D7: Label how each finding was established

- **Why:** in a long session, it becomes hard to tell which facts the user stated, which the agent derived from data, and which the agent asserted from its own knowledge. Findings written by an agent read the same either way.
- **Scope:** a required tag on each grill brief fact and each finding draft: `human-stated`, `agent-derived` (with the artifact), or `agent-asserted` (with a source, or `none`). Grill's brief and verify's report show the counts; `agent-asserted` without a source is flagged.
- **Out of scope:** writing `.living/`; Mycelium's ledger format stays as is (the tag goes in text it already accepts).
- **Depends on:** none.
- **Constraints:** complement Mycelium, never override its formats. Tags must be cheap to read: one word, not a paragraph.
- **Grill prompt:** `/mycelium-extra:grill Add a provenance tag (human-stated, agent-derived, agent-asserted) to each fact in grill's brief and to finding drafts, and make verify count them. Check what Mycelium's findings format allows without changing it.`
- **Acceptance:** a grill brief on the fixture tags every fact; an untagged or unsourced `agent-asserted` fact is flagged.
- **Tests:** contract test in `skills/grill/tests/` that the brief template carries the tag.
- **Effort:** S.
- **Status:** done (0.9.35). Grill's brief ends each Evidence fact with `[human-stated]`, `[agent-derived: <path>]`, or `[agent-asserted: <source>]` plus a `Facts:` count line; `verify` counts the tags in the frozen plan's Evidence and the analysis doc's Key Findings as info and flags untagged and unsourced facts. Mycelium findings get the tag at the end of the ledger's Result cell, through the gate's post-run notice.

### D8: The user states the research question first

- **Why:** when the agent drafts the question, the user tends to accept a version that fits the data at hand rather than the one they meant. Asking first anchors the plan to the user's intent.
- **Scope:** grill asks the user for the question and the claim they hope to make, in their own words, before it reads the data or proposes anything, and quotes it at the top of the brief. If the user declines, the brief says so.
- **Out of scope:** judging the question's quality.
- **Depends on:** none.
- **Constraints:** one question, not a questionnaire; the user may answer in a sentence.
- **Grill prompt:** `/mycelium-extra:grill Change grill so it asks for the research question and the hoped-for claim in the user's words before reading data or proposing anything, and quotes the answer at the top of the brief.`
- **Acceptance:** a grill session on the fixture opens with the question; the brief quotes it verbatim.
- **Tests:** contract test on SKILL.md section order.
- **Effort:** S.
- **Status:** done (0.9.35). Grill's section 0 asks in one free-text message, before reading anything, skips what the request already states, and does not count toward the five-question cap.

### D9: Enforce the reason on each default

- **Why:** grill already asks for `default: <reason>` in the plan's Source column and a one-line entry per default under Assumptions and risk. Nothing checks it. A default written as `default:`, `default: standard`, or `default: common practice` gives a reviewer nothing to push back on and hides when the default is wrong for this data.
- **Scope:** a stdlib check, run by plan-review on the plan it reviews and by verify on the frozen plan, that flags a `default:` with no reason, a reason under a few words, or a reason from a short list of empty phrases (`standard`, `common practice`, `best practice`, `typical`). Each flag names the plan row. Advisory: it reports, it does not block approval.
- **Out of scope:** changing which choices may default; judging whether a reason is correct.
- **Depends on:** none.
- **Constraints:** the empty-phrase list lives in one file a user can read and extend. `source:` rules in analysis-decisions.md stay as they are.
- **Grill prompt:** `/mycelium-extra:grill Grill already requires default: <reason>, but nothing checks it. Add an advisory check, run by plan-review and by verify, that flags a default with no reason or an empty reason such as "standard", naming the plan row. Read SKILL.md's Plan and Assumptions sections first.`
- **Acceptance:** a plan row with `default:` alone or `default: standard` is flagged by row; `default: BH, since the tests are not strongly dependent and no weighting is planned` is not.
- **Tests:** unit tests for the check; one case in `skills/plan-review/tests/test_plan_review.py`.
- **Effort:** S.
- **Status:** done. `skills/plan-review/scripts/default_reasons.py` (run by plan-review on the draft; verify imports it from the plugin root and reports each flag as an `info` finding, status unchanged; a missing or failing checker is a verify gap). A reason needs three words besides filler, and three besides an empty phrase.
