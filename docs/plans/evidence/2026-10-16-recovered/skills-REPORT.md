# Owned skill stress test, 2026-10-16

Scope: the actual checkout has 11 skills total; this worker owns 10, excluding verify. No pre-existing owned skill files were dirty. Worker never edited hooks, verify, manifests, versions, personal installs, or top-level docs. All disposable data/projects lived under /tmp. Baseline shared checkout dirty files were observed and preserved.

## Results

Final owned suites on system Python 3.6.8, LC_ALL=C, PYTHONCOERCECLOCALE=0, PYTHONUTF8=0, with the existing R4_51/bin prepended to PATH: 114 discovered, 107 passed, 7 skipped (h5py unavailable). R stub validation ran with R4_51 and passed. Individual logs are *final-ascii-r.log. Baseline: 101 discovered, 93 passed, 8 skipped (h5py and absent Rscript on default PATH). No dependency installed.

| Skill | Evidence and exercised behavior | Result and scope |
|---|---|---|
| grill | 10 reference/contract tests; read SKILL plus referenced source links; cross-skill gates, decision list and run-plan references | Static contract checks passed; actual interactive question limits, source grounding and readiness decisions need native behavioral qualification |
| init | 19 tests: defaults, repeat/nested initialization, missing paths, dry run, ignore handling, options, tool discovery/failure/preservation, version notices, actual gate-denial subprocess, invalid hours and malformed persisted object shapes | Passed; settings support --root, --paths, --commands, --hours, --tools, --scilintr, --rscript, --dry-run; host hook registration owned by root |
| new-analysis | 17 tests: Mycelium/ordinary trees, dry run, overwrite refusal, step order, links/missing/colliding links, template lookup, notebook, fail-loud Python/R stubs, ignored paths, workflow chains, gate-compatible command form, quote/backslash path escaping | Passed including actual R stub. Wrapper tested with simulated Snakemake. Full actual Snakemake execution remains unverified in worker scope |
| plan-review | 9 default-reason tests, 6 procedural contract tests, 11 pre-send tests; secrets/contact/home/identifier patterns, masked output, required user send authorization, reviewer roles/unavailable status, quoted paths, BOM and missing-table gaps | Passed deterministic helper and static contract checks; no paid reviewer or external send, no actual independent adjudication |
| data-contract-check | 32 tests, 7 H5AD-specific skips: schema, cohort, units/crossover, pairing, batch/confounding/imbalance, filters, no rows, missing columns/files, severity cannot downgrade, bad types, duplicate headers; 96 additional bounded malformed-type mutations, no unhandled exceptions | 25 passed, 7 unavailable; CSV/TSV exercised. H5AD actual encodings unavailable because h5py missing; do not call them tested |
| decision-status | 10 tests: heading variants, dates, positional-ID warnings, raw fields, no inferred status, tags/body retrieval, ASCII output, invalid regex and nested code fences | Parser passed; scoped supersession, contested decisions and append-only human resolution remain procedural contracts |
| handoff | Read contract: status/commit/diff, overwrite prior handoff, preserve locked choices/dead ends, verbatim pending plans, fresh-session approval and no Mycelium file writes | Static review only; actual state reconstruction/pending-plan handoff in a new native session needs behavioral qualification |
| idea | Read contract and actual tested Mycelium 0.7.2 upsert helper. Synthetic repeated title: old Title key retains 1 of 2 rows, new exact File key retains both; helper needs newer Python, exercised with existing Python3.11 | Helper integration passed; agent capture/no-question behavior and concurrent slug allocation not native-session tested |
| idea-triage | Read rubric and contract, verified integration with idea's File-keyed update, explicit park-all no writes, missing-file gap, unknown ratings, user choice before starts | Static review + actual underlying registry helper; ranking and user-directed mutation remain unverified native behavior |
| harden | Read full contract: concrete candidates, exclude analysis edits, failed reproduction and passing current result, leave learning ambient on failure, confirmed narrow append | Static review only; no user's learning selected/modified and no claim of actual behavioral compliance |

## Reproduced defects and fixes

1. Contract trust boundary could pass an empty check list or a cohort check with no assumptions and enable crossover relaxation with the string "false". It also crashed or coerced wrong filter/check/count/column types. Added explicit shape/type validation before checking data, required nonempty check lists and meaningful cohort assumptions, exact Boolean relaxation and integer counts. Malformed inputs now return clear usage errors without traceback. Optional empty within/no_missing lists remain valid. Scalar missing cohort levels now render as a single level, preserving the already supported as_list behavior.
2. Duplicate CSV/TSV headers overwrote a column and could report a false pass. Duplicate headers now produce an explicit unreadable-table gap.
3. init --hours nan/inf raised tracebacks; persisted null/list gate/tools objects crashed. Hours now must be finite/positive; existing malformed gates return clear failure and remain byte-for-byte untouched. Nonobject tool files are explicitly reported and rebuilt only from checked tools.
4. Quoted/backslash data basenames generated invalid Snakefile literals and notebook Python. Used JSON string literals for generated data paths and notebook INPUT; escaped the Snakefile docstring name/path substitutions.
5. Pre-send checks silently missed participant IDs in backticked/quoted paths with spaces and BOM-prefixed CSV ID headers, and omitted missing named tables from coverage gaps. Tokenize quoted/backticked paths, read BOM-aware headers, and report missing tables as unchecked.
6. Idea and triage instructions keyed upserts by Title although slug collisions create distinct files. Both now key by the exact File cell with --key-column 7, including fallback edits. Existing tested Mycelium helpers support this option; observed 1-row loss before versus 2 rows retained after. Added empty-slug/table-cell rules, project plugin-root discovery, and removed inaccurate fixed Python minimum for external helper.
7. Decision parser could turn code-fenced sample headings into apparent real decisions when nested fences used another marker or shorter fences. Track opening marker type/length and close only a matching fence. Invalid regex search terms now return a clear usage error.
8. Coherence: idea says no analysis code (it legitimately runs metadata/table helper commands); triage park all explicitly writes nothing; data-contract report statuses include gap.

Each code defect has a focused regression with before-failure evidence. Logs: *.regression-before.log, init-shapes.before.log, decision-status.before.log, cohort-noop.before.log; original raw reproductions are *.reproduction.log. Static instruction changes have helper reproduction evidence where applicable; they do not establish native host compliance.

## Reproduction

Run each suite using the actual CI file-by-file convention:

```bash
for t in skills/data-contract-check/tests/test_*.py skills/decision-status/tests/test_*.py skills/grill/tests/test_*.py skills/init/tests/test_*.py skills/new-analysis/tests/test_*.py skills/plan-review/tests/test_*.py; do
  LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0 PATH=<ACCOUNT_HOME>/conda/envs/R4_51/bin:$PATH /usr/bin/python3 "$t"
done
python3 /tmp/mycelium-audit-20261016/skills/integration_checks.py
```

integration_checks.py creates ordinary and Mycelium temporary Git projects, initializes, dry-runs/scaffolds, validates links and generated Bash syntax, launches real run.sh with a simulated Snakemake, and runs all five contract-check kinds on a synthetic balanced longitudinal cohort. Also exercises the installed Mycelium registry helper with both keying strategies. Results in integration-results.json. This is not a claim of full workflow engine execution or native skill adherence.

## Remaining limitations

- Agent-driven skills are mainly instruction contracts. Static checks, helper tests and sample integration do not prove the host agent follows question caps, confirmation boundaries, sound scientific interpretation, handoff fidelity or append-only updates.
- Native reviewer/Claude/Codex behavior, external review delivery, schedulers, heavy analyses and provenance are owned by other workers/root or explicitly unavailable, not qualified by this worker.
- Presend remains pattern-based: short IDs under 3 characters, free text identifiers, unsourced input tables and re-identification can escape it; this is documented and the integration observes its short-ID limit.
- Batch checks cover documented nesting/isolated-level rules, not arbitrary contrast estimability or a disconnected multi-level design graph. Contract passes do not establish scientific validity.
- Scaffold writes are exclusive and refuse existing nonempty folders; fault-injected mid-write rollback and cross-agent slug allocation were not added or claimed.
- No commits, pushes, external messages, paid reviews, production jobs, configuration installs, or dependency installs.
