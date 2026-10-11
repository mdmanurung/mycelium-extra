# Implementation map

What the roadmap contains, and the order to build it in. Status as of 2026-10-04, against
`main` at `3a11123` plus the 22-patch series in this folder.

33 tasks total: **10 done** (in the series plus the locale fix), **3 partial**, **20 open** (2 of which are maintainer
decisions, not builds). Rough remaining effort: ~8 S + ~10 M + ~3 L, about **4 focused weeks**.

---

# Part 1 — What the improvements actually are

## Already built, in the 22 patches

| Theme | What landed |
| --- | --- |
| Shareable | MIT `LICENSE` (A1), `CHANGELOG.md` (A3), README split into a 108-line landing page plus `docs/` (T0, B1, B3, B4) |
| Gate correctness | Three false positives fixed, so harmless commands stop being blocked (E2) |
| Receipt correctness | `sbatch --chdir` with `--wrap`; exit status taken from the hook event, and `PostToolUseFailure` registered so a **failed run finally leaves a receipt**; Codex's lack of receipts documented (E3 a/c/d) |
| New checks | `data-contract-check` reads `.h5ad` `obs` and warns on graded batch imbalance (D6); `default:` reasons are enforced, so "default: standard" gets flagged (D9); an LLM failure-mode checklist in grill (D5) |
| Testing | The C1 fixture Mycelium project and the end-to-end harness — the first test of the whole chain rather than each skill alone |

## What the roadmap plans next

**The through-line.** Today the package proves *the right code ran on the right data*. The roadmap
extends it to prove *what is written about the results matches the results* (D1-D9), and then that
*the human is still actually checking* (D10-D12).

1. **Make it shareable** (A2, A4, A5, A6) — CI on Python 3.6 and latest; a GitHub description and
   topics; `init` warning when the installed Mycelium is outside the tested range; a worked example
   that is a real transcript, not hand-written.
2. **Close reproducibility gaps** (C2, C3, E1, E3b, E5) — the last receipt gap (a Snakemake rule's
   inputs counted as runs); recording pip packages and per-rule conda envs, which today silently
   vanish from provenance; an optional fail-closed gate for labs; an audit of what
   `plan-review` actually sends off the machine; four parked `.Rmd`/`.qmd` chunk-lint cases.
3. **The mindfulness core** (D1-D4, D7, D8) — the biggest new idea.
   - **D1 claims checker**: an agent writes "312 genes were differentially expressed"; the table has
     287 rows passing that threshold. Nothing catches this today. D1 extracts numeric claims,
     locates the cited artifact, and matches the value. Flagship task, effort L.
   - **D2 citations**: resolve every DOI/PMID/arXiv ID and compare title and first author, because
     LLMs invent plausible references.
   - **D3 disclose**: draft the "how AI was used" methods paragraph from the receipts, so it is not
     written from memory (which understates the agent).
   - **D4 multiplicity**: count how many runs and threshold revisions preceded the reported result.
   - **D7/D8**: tag each fact `human-stated` / `agent-derived` / `agent-asserted`; make grill ask
     for the research question in the user's words before it reads any data.
4. **Anti-gaming** (D10-D12) — make oversight drift visible to the researcher themself: approval
   latency, a one-question comprehension checkpoint on long plans, approval expiry by reuse count,
   and seeded-error audits with a personal dashboard. All local, off by default, disclosed at
   install, never reaching provenance or `.living/`.

---

# Part 2 — The order to build it in

## Do now

- [x] **Fix the locale crash** — done, patches 0023-0024 (v0.9.31). `verify.py` is now pure ASCII
      and `new-analysis` names `utf-8` on its template reads and writes. All 12 test files pass on
      a real Python 3.6.8 interpreter. **(was S)**
- [x] **Finish the encoding sweep** — done in v0.9.32 (text `open()`, subprocess decoding, and an ASCII-stdout guard in the four printing scripts). **(S)**
- [ ] **Decide: is a missing exit status a gap or info?** The series makes it a gap, so `CONFORMS`
      becomes `CONFORMS_WITH_GAPS`. Your live exposure is nil (3 receipts, all explore), and
      committed provenance does not flip. One-word change either way. **(S)**
- [ ] **Land the series** — `git switch -c improvements && git am patches/*.patch`, then re-run the
      suite. **(S)**
- [ ] **A3 tags** — create `v0.9.16`..`v0.9.30`; commands are in `notes/docs.md`. **(S, maintainer)**
- [ ] **A4 description and topics** — the `gh repo edit` line is in `APPLY.md`. **(S, maintainer)**
- [ ] **A1 name** — `LICENSE` says "Mikhael Dito Manurung", the manifests say "Mikhael Manurung".
      Pick one. **(S, maintainer)**

## Next — the foundation everything else needs

C1 is the keystone: **A2, A6, C3, D1, D4 and E4 all depend on it.** Build it before anything in the
later sections.

- [x] **C1 steps 3-5** — done (`ac83c96`, `716a149`, `2c19fb1`): 49 defects, 5 catalog tests, 3 ablations. **(L)**
- [~] **A2 CI** — written, checked locally (`.github/workflows/ci.yml`); first GitHub run pending a push. GitHub Actions on Python 3.6 and newest, plus `gate_diff.py` against the PR base.
      Hosted runners no longer ship 3.6, so this needs a container. Fix the two CI-candidate tools
      first: `check_links.py` with no args exits 0 having checked nothing, and flags the
      `@@DOC@@` template placeholder. **(M, needs C1)**
- [x] **E3b Snakemake rule inputs counted as runs** — done in 0.9.33 (`ee9a498`). **(M)**
- [x] **E3 gate_diff scenarios** — E2 commands, twins, hook events; E3 done. **(S)**
- [x] **E1 pip packages in conda envs** — done in 0.9.37 (`ea2cc76`..`185d791`, plan 42fd5ffd). **(M)**
- [ ] **E1b Snakemake per-rule conda envs** — split from E1; return when a `--use-conda` pipeline
      runs under verify. **(M)**
- [x] **B2 move the dated verify history to the changelog** — unblocked now that A3 has landed. **(S)**

## Then — robustness and polish

- [ ] **C2 optional fail-closed gate** — `on_error: "deny"` in `gate.json`, default unchanged. **(S)**
- [ ] **A5 Mycelium version check in `init`** — notice only, never blocking. **(S)**
- [ ] **E5 parked chunk-lint cases** — document-level `eval: false`, `child=`, `read_chunk`,
      `engine=`. Check a real repo uses them first. **(S)**
- [ ] **E4 exercise the untested features** — hints, harden, verify `stale`/`status`/`explore`, the
      R scilintr path, R notebooks, `.Rmd` chunks. Record expected vs observed; fix nothing. **(M, needs C1)**
- [ ] **A6 worked example** — a real end-to-end transcript on the fixture. **(M, needs C1)**
- [ ] **C3 plan-review redaction audit** — the one task about data leaving the machine. **(M, needs C1)**

## Later — the mindfulness core

- [x] **D1 claims checker** — done in 0.9.34 (`0e866fa`..`ffb4037`): a verify stage checking
      `<!-- claims -->` blocks whose lines name their cell; e2e V-21..V-23, V-09 now blocks. **(L)**
- [x] **D7 provenance tags on facts** **(S)** and **D8 user states the question first** **(S)** —
      both independent of C1, so they can slot in any time.
- [x] **D4 multiplicity view** **(M, needs C1)**
- [ ] **D2 citation resolution** **(M, needs D1)**
- [ ] **D3 disclose skill** **(M, needs D1 and A3)**

## Last — anti-gaming

Only meaningful once C1 and D1 are real.

- [ ] **D12 seeded-error audits and the personal dashboard** **(L)**
- [ ] **D10 comprehension checkpoint and approval latency** **(M, needs D12)**
- [ ] **D11 approval expiry by reuse count** **(S)**

## Decisions, not builds

- [ ] **B5** — does `HANDOFF.md` stay committed? Options: keep as is; move the lasting sections to
      `docs/decisions.md` and gitignore it; or mark the session-state section as such.

---

## How to run each task

The roadmap is built so each task pastes straight into the tool itself: every entry in
`docs/roadmap/0*.md` carries a **Grill prompt** field. The loop is

```
/mycelium-extra:grill <the task's grill prompt>
/mycelium-extra:plan-review          # optional
approve plan <hash>
<run it>
/mycelium-extra:verify <hash>
```

Two rules from the roadmap's own principles bind every task here: **one feature, two commits**
(`feat(...)` then `chore: bump version` across the three manifests), and **run
`hooks/tests/gate_diff.py` before and after any change to `hooks/gate.py`**, where only the
decisions you meant to change may differ.
