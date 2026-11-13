# Stage recipes

Read this when mapping stages (step 2). Each recipe says what to ask the user and what the stage logs. Commands below are common ones; confirm them against the user's cluster before writing them in. Where a site differs, write "check your cluster's documentation" and ask.

## SLURM account or partition

- Ask: which account, which partition, who approves requests (a person, a ticket system, an email). Do not guess the site's process or address.
- Human steps: submit the request through the site's channel; later, list what they have with `sacctmgr show assoc user=$USER format=account,partition` (check that the command is allowed on this cluster).
- End with `sbatch_test` on the granted account and partition (`MX_SBATCH_OPTS`), so success means a job ran.
- Log: the account and partition names, the request date, the test job result.

## Environment (conda, pixi, uv)

- Ask: which manager, which file pins it (`environment.yml`, `pixi.toml`, `pyproject.toml` plus lock), and where it installs (home quota on HPC is small; ask for a project or scratch path).
- The version pins are the user's. If the file does not pin, list "pin the versions" as an impactful-choice row and ask.
- Human steps: run the install command on a login node or in a job, per site rules.
- Check: a one-line import or `--version` test through `sbatch_test`, so the compute node sees the same environment.
- Log: the file used, its sha256 (`sha256sum file`), the install path.

## Large or controlled-access data

- Ask: the accession or portal, the access status (public, or approved by whom), the target folder (outside the repository, under `data/` as links), and where the checksums come from (the provider's manifest, or `MISSING`).
- Controlled access: open the portal URL, say "check the current page" for the application and download steps, then `record_access "<dataset>"`. Remind the human that the consent and disclosure terms are theirs to follow. Enforce nothing.
- Download: show the exact tool command (`prefetch`, `aws s3 cp`, `wget`, vendor client) only when the user or the portal documentation gave it. Run long transfers as a job, not on the login node.
- Check: `verify_checksums <manifest> <dir>`. Without a manifest, log `no provider checksum` and the sha256 you computed, and say so.
- Never delete or overwrite existing data. A re-download goes to a new folder.
- Log: accession, date, path, checksum result, access decision.
- Follow-up to suggest: `/mycelium:ingest` to register the data.

## API keys

- Ask: which tool, what the key unlocks, whether a free tier is enough.
- Human steps: open the provider's account page, "check the current page" for where keys are shown.
- `ask_secret NAME`, then `write_secret NAME "$NAME"`. The tool reads it from the secrets file: `set -a; . "$SECRETS_FILE"; set +a` in the job script, or the tool's own config path when it names one.
- Log: the key name and where it is stored.

## lucid-coder.yaml

- The wizard checks the file exists and parses; it does not write analysis choices.
- Follow-up to suggest: `/lucid-coder:align`, which the user runs. Say what it will ask.
- Log: that the file was created or confirmed, with its path.

## First-time git and GitHub auth

- Human steps: `git config --global user.name` and `user.email` (the user types their own); create an SSH key with `ssh-keygen -t ed25519` (the passphrase is entered by the human); add the public key on the GitHub page ("check the current page" for the SSH keys settings); test with `ssh -T git@github.com`.
- Never read or print the private key. Show only the public key path.
- Log: key file path, the test result.

## Register data in Mycelium

- Suggest `/mycelium:ingest` as the last stage. The wizard does not run it and does not write to `.living/`.
