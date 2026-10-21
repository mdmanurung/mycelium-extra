# Analysis Journal: validation receipt

[Back to the plan](2026-10-20-analysis-journal.md)

Base `72b85c3`. Everything below ran on synthetic data; no scientific or scheduler job ran.

## Checks and outcomes

| Check | Result |
|---|---|
| `skills/track-changes/tests/test_journal.py`, Python 3.12 | 11 tests OK |
| Same, Python 3.14 | 11 tests OK |
| `skills/track-changes/tests/test_track_changes.py` | 41 OK |
| Report fixes 5; verify 267; provenance 5; gate 477 (2 skips) | OK (earlier sweep, source unchanged except `journal.py` hardening below) |
| End-to-end 111 (2 skips); fixture data 3; ablations 17/17 bite | OK |
| Gate-diff against the pinned base, Python 3.12 and 3.14 | exit 0, 57 accepted differences, oracle unchanged |
| Pinned Sphinx build with `-W` | OK |
| Real Firefox 140: desktop 1280, narrow 390, 200% zoom, keyboard, search, JSON invariance | OK on the large and the missing-source example |

Hardening added last: a nested `plans: null` in a launch record, and non-list `findings` in a saved verification or a checkpoint, now degrade to partial coverage or a rejected checkpoint instead of raising. The new test fails without the fix.

## Resume verification, 2026-10-21

The feature (`5fb02a0`) and separate 0.15.0 bump (`189d352`) were already
committed when work resumed. The isolated `analysis-journal` branch incorporated
the newer main documentation at `716e15c`; those changes are preserved. Compared
with audit `a8830d8`, current source also includes opt-in write confirmation and
its init diagnostic fixes. This feature keeps those newer behaviors.

A follow-up closes the remaining nested-launch coverage gap: invalid run plan
lists and invalid ambiguous-attempt collections now mark launches partial rather
than silently skipping them as available. The regression asserts both visible
partial coverage and absence of an invented launch. No gate, approval reader,
publication protocol or oracle changes accompany this correction.

Run these from the isolated checkout with the available supported interpreter:

```bash
python3.12 skills/track-changes/tests/test_journal.py -v
python3.14 skills/track-changes/tests/test_journal.py
python3.12 skills/track-changes/tests/test_track_changes.py
python3.12 skills/track-changes/tests/test_report_fixes.py
python3.12 skills/verify/tests/test_verify.py
python3.12 hooks/tests/test_provenance.py
python3.12 hooks/tests/test_gate.py
python3.12 tests/test_versions.py
python3.12 tests/check_links.py $(git ls-files '*.md')
/tmp/journal-docs/bin/python -m sphinx -b html -W --keep-going -c docs . /tmp/journal-resume-sphinx
```

The documentation environment uses `docs/requirements.txt`. Python 3.9 is not
installed locally. The earlier full CI-glob sweep covered 39 scripts; its init
failure was fixed by incorporating `72b85c3` and the 33-test init suite passed.
Optional upstream/tool-dependent cases retain their reported skips. The follow-up
changes only Journal collection and its regression; prior gate-diff, end-to-end,
ablations and browser results above remain applicable to unchanged source.

Resume outcomes: Journal 11/11 on Python 3.12 and 3.14, plus the final nested-run
regression on both interpreters; track-changes 41/41, report fixes 5/5,
verify 267/267, provenance 5/5 and gate 477 (2 skips). Version consistency passed; all 446
Markdown links resolved; the warning-as-error Sphinx build passed against the
newer documentation. The standalone consumer validated the committed example
(`CONFORMS_WITH_GAPS`, independently `not qualified`); a read-only collection of
its portable records loaded 167 events and two checkpoints without local state.

The earlier full-sweep skips were gate 2, data-contract 20, scaffold 1,
end-to-end 2, recipes 1 and single-cell conventions 7. Firefox was re-run on the
large example after resume: overview budget, two-step evidence access, return
navigation, all-history search, presentation/export invariance, real keyboard
operation and desktop/narrow overflow checks passed. The initial state contained
three concerns, zero routine rows and zero expanded disclosures.
Fresh runs on the missing-source example and at actual 200% zoom also passed;
the zoom run confirmed DPR 2, a 640 CSS-pixel viewport and no page overflow.
The missing-source overview retained six incomplete/absent source groups and
missing-completion/conflict notices even with no new concerns in its period.

## Screenshots

`../examples/analysis-journal-overview.png`, `../examples/analysis-journal-evidence.png`; receipts for narrow and 200% zoom are in `../examples/qa/`.

## Limits

- A checkpoint is a compact observation, not tamper-proof and not a complete-history certificate.
- Unavailable original evidence is stated as unavailable; absent SHA256 is never invented.
- Browser checks were Firefox only. Skipped suites (Node adapter on other versions, optional suites) are listed in CI output.
- Journal timestamps are source-specific; unknown occurrence stays unknown.
