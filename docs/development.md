# Development

[Back to README](../README.md)

**Tests:** `python3 skills/<skill>/tests/test_*.py` and `python3 hooks/tests/test_gate.py`. The end-to-end suite on the fixture project is `python3 tests/test_end_to_end.py` (about 40 s) with `python3 tests/test_fixture_data.py`; `python3 tests/e2e/ablate.py` checks that the defect cases still depend on the guards they name ([design](design/c1-fixture-project.md)).

`python3 tests/test_versions.py` checks that the three manifests and the newest `CHANGELOG.md` heading name the same version, and `python3 tests/check_links.py $(git ls-files '*.md')` that every relative link and anchor resolves.

CI (`.github/workflows/ci.yml`) runs all of the above on every push to `main` and every pull request, in the official `python:3.6-bullseye` image under `LC_ALL=C` and in `python:3.14-bookworm`, since hosted runners no longer ship 3.6. On a pull request it also runs `gate_diff.py --base` against the PR's base commit, so an intended gate change shows as a red check to explain in the PR.

Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: it sends the same events to the committed gate and the working tree and must report every case identical, except the decisions you meant to change.

Hooks call bare `python3`, which is 3.6 on some HPC systems, so keep every script 3.6-compatible; the gate tests compile them all under `python3.6` when it is installed.

Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change. The same commit adds a [CHANGELOG.md](../CHANGELOG.md) entry for the new version.
