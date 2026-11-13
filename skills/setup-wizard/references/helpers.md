# Wizard library helpers

Read this when authoring stages. The library lives above the `STAGES` marker in `templates/template.sh`.

| Helper | Use |
|---|---|
| `stage "Name"`, `say`, `step`, `note`, `warn`, `ok` | Print the stage frame and lines. `step` is an action the human takes. |
| `open_url URL` | Print the URL and open it when a browser exists. On a headless node it says to open it on your own machine. |
| `ask KEY "Prompt"` | Visible input into `$KEY`. A value already in the environment is the default. |
| `ask_secret KEY "Prompt"` | Hidden input into `$KEY`. Enter keeps the value already in the secrets file. |
| `write_secret KEY "$KEY"` | Upsert into `SECRETS_FILE` at mode 600. Refuses a path inside a git repository that git does not ignore. Logs the name, never the value. |
| `confirm "Question"`, `pause "Message"` | A y/N gate and a wait. Put `confirm` before anything irreversible. |
| `log_setup "text"` | Append one dated line to `SETUP_LOG`. It refuses text holding a secret of 6 or more characters entered in this run. |
| `skip_if_done NAME`, `mark_done NAME` | Offer to skip a finished stage on a re-run. |
| `record_access "dataset"` | Log who approved access and the date. Enforces nothing. Reads `ACCESS_APPROVER` and `ACCESS_DATE` when set, else asks. |
| `sbatch_test LABEL SECS 'command'` | Write `logs/setup-jobs/LABEL.sbatch`, show it, submit after a confirm, poll `squeue` then `sacct` up to SECS, show the log tail. Returns 0 only on COMPLETED. On a timeout it leaves the job and prints the `scancel` line. |
| `verify_checksums MANIFEST [DIR]` | `sha256sum -c` inside DIR. On a mismatch it logs, prints the bad lines and stops. It never deletes or renames. |
| `finish` | Closing summary: log lines, secrets written, skipped items. |

## Settings (environment)

| Name | Default | Meaning |
|---|---|---|
| `SETUP_LOG` | `logs/SETUP.md` | Setup log. No secrets. |
| `SECRETS_FILE` | `~/.config/mycelium-extra/setup.env` | Secrets file, mode 600. |
| `MX_SBATCH_OPTS` | empty | Extra `sbatch` options, for example `--partition=short --account=lab`. |
| `MX_TEST_WALLTIME` | `00:05:00` | Walltime of the test job. |
| `MX_POLL_SECS` | `5` | Seconds between job polls. |
| `MX_WIZARD_YES` | unset | **Test only.** Auto-confirms every gate, skips pauses and browser opening. Never set it in a real run. |

## Tests

`python3.11 skills/setup-wizard/tests/test_template.py` runs `bash -n`, the example stage, and each helper with stubbed `sbatch`, `squeue` and `sacct`.
