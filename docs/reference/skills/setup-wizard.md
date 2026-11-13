# setup-wizard

Generates a bash wizard that walks you through cluster setup steps only you can do, and records what you did. Adapted from Matt Pocock's wizard skill (MIT).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

```text
/mycelium-extra:setup-wizard
```

The agent scopes the setup from the repository, confirms the stage list with you, writes `setup/<topic>.sh`, checks it with `bash -n` (and `shellcheck` when installed), and tells you how to run it. It does not run the wizard, because the wizard waits for you.

```bash
bash setup/<topic>.sh
```

Run it from the project root on a login node. It is safe to stop and re-run: finished stages offer a skip.

## What a wizard can cover

| Setup | What the wizard does |
|---|---|
| SLURM account or partition | Says what to request and how to list what you have; ends with a test job |
| Environment (conda, pixi, uv) | Shows the install command for your pinned file; tests it on a compute node |
| Large or controlled-access data | Opens the portal page, records the access decision, verifies checksums |
| API keys | Reads the key hidden and stores it at mode 600 outside the repository |
| `lucid-coder.yaml` | Checks the file; suggests `/lucid-coder:align` for you to run |
| First-time git and GitHub auth | Walks the key setup; you type passphrases |
| Data in Mycelium | Suggests `/mycelium:ingest`; does not run it |

## Helpers in the script

Stage progress, confirm gates, URL opening (WSL included), hidden secret entry and idempotent writes come from the original template. The cluster helpers are new: `sbatch_test` submits a test job after your confirm and polls `squeue` then `sacct` with a timeout; `verify_checksums` runs `sha256sum -c` and stops on a mismatch; `log_setup` and `record_access` append to the setup log. The full list is in the skill's `references/helpers.md`.

## Reads and writes

Reads the repository files named above to scope the stages. Writes `setup/<topic>.sh` (not under `analysis/` or `nbs/`, which are gated). When you run the wizard it appends to `logs/SETUP.md` (or the `SETUP_LOG` you set) and `logs/setup-jobs/` for test jobs, and writes secrets only to `SECRETS_FILE` (default `~/.config/mycelium-extra/setup.env`, mode 600). It refuses a secrets path inside a git repository unless git ignores it. The log holds names, paths and dates, never secret values.

## Default on or off

Off until you type the skill. The script it makes does nothing until you run it.

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| No secret reaches the log or the screen; the secrets file is mode 600 and outside the repository or ignored | Enforced by the script |
| A confirm sits before each job submission; checksum mismatch stops the script; nothing is deleted | Enforced by the script |
| `MX_WIZARD_YES=1` removes the confirms | Test-only flag; do not set it in a real run |
| Following the consent and disclosure terms of controlled-access data | Yours. The wizard only records who approved and when |
| Writing "check the current page" where the agent has not seen the page | The agent's instruction |
| Not running the wizard end to end | The agent's instruction |

See [handoff](handoff.md) for resuming work in a new session, and [new-analysis](new-analysis.md) for the folder the setup log lives in.
