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

## Screenshots

`../examples/analysis-journal-overview.png`, `../examples/analysis-journal-evidence.png`; receipts for narrow and 200% zoom are in `../examples/qa/`.

## Limits

- A checkpoint is a compact observation, not tamper-proof and not a complete-history certificate.
- Unavailable original evidence is stated as unavailable; absent SHA256 is never invented.
- Browser checks were Firefox only. Skipped suites (Node adapter on other versions, optional suites) are listed in CI output.
- Journal timestamps are source-specific; unknown occurrence stays unknown.
