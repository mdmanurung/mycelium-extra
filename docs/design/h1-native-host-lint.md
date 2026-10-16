# H1: lint-on-write in a native Claude Code session

Record of 2026-10-16 for the open host-qualification item (`docs/plans/2026-10-15-remaining-qualification.md`, H1). Each run was a real `claude -p --plugin-dir <repo> --include-hook-events` session (Claude Code 2.1.301) in a scratch project with real Python scilintr 0.1.2 in a venv; the hook ran under the system `python3` 3.6.8.

| Feature | Observed |
|---|---|
| Write-time lint (`PostToolUse` on `Write`) | The hook's `additionalContext` reached the model. In one run the agent quoted both findings back verbatim. |
| Stop line (user-only) | A `Stop` hook response carried `systemMessage` naming `02_fit.py (broad-exception, silent-pass)`. |
| `lint_before_run: "block"` | With a plan approved for the script, `python3 analysis/a/02_fit.py` was denied before running, in a different session from the write. The agent saw the reason and did not work around it. |
| `lint_before_run: "warn"` | The command ran (it failed on a missing `pandas`, unrelated); the agent saw and quoted the message. |
| `lint_before_stop: true` | The first Stop returned `decision: block` with the findings; the agent took one more turn and the session then ended. It was told to leave the file exactly as given, so it fixed nothing. |

Not observed: Codex. Installing the plugin into the user's Codex configuration is a native host change, so only the Codex launcher path is covered, by `hooks/tests/test_codex_gate.py`. How the host draws a `systemMessage` to a person at a terminal was also not seen, only that the hook returned it.

## A shared lint cache was not built

The card lints the code a plan names, the write hook lints the files just touched, and `verify` lints the whole analysis folder. Those are three different file sets, and scilintr has cross-file rules, so one file's result cannot be reused for another set. A cache keyed on the whole set would rarely hit, and a stale entry would show code as clean that a newer scilintr or an edited waiver would flag. A false "clean" is the one error `verify` is built to avoid, so the saving (one R start, 1.3 to 4.4 s) is not worth it.
