# Development

[Back to README](../README.md)

**Tests:** `python3 skills/<skill>/tests/test_*.py` and `python3 hooks/tests/test_gate.py`.

Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: it sends the same events to the committed gate and the working tree and must report every case identical, except the decisions you meant to change.

Hooks call bare `python3`, which is 3.6 on some HPC systems, so keep every script 3.6-compatible; the gate tests compile them all under `python3.6` when it is installed.

Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change.
