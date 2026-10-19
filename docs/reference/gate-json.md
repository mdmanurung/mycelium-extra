# gate.json reference

`.mycelium-extra/gate.json` is the one settings file of the approval gate. Its existence is what switches the gate on: a repository (or any folder below it) with no `gate.json` is not gated, and every hook returns at once.

- `{}` is a valid file and means "all defaults".
- `init` writes the file once and never changes it afterwards; after that you edit it by hand ([init](skills/init.md)).
- A missing key uses its default. An unknown key is ignored by the gate; `init --diagnose` reports it as a possible typo.
- A file that is not valid JSON is an internal gate error and follows `on_error` (below).
- Where the gate checks a value, an invalid one never aborts a hook. The gate uses the default for that key and shows one notice naming the key and what it accepts, at the next prompt and at the next turn end.

To see the effective values, with invalid ones flagged, run `init --diagnose` ([init](skills/init.md)). It reads and writes nothing.

## The 15 keys

| Key | Type | Default | Accepts | What it does |
|---|---|---|---|---|
| `gated_paths` | list of strings | `["analysis/**", "nbs/**"]` | globs relative to the project root | Scripts under these paths cannot run until an approved plan names them in its Step column. |
| `gated_commands` | list of strings | `["sbatch", "snakemake", "nextflow"]` | command words | These launchers cannot run until an approved plan's table contains the command word. |
| `approval_hours` | number | `24` | 0 or more | How long an approval covers runs. `0` expires every approval at once. Approval files are never deleted. |
| `on_error` | string | `"allow"` | `"allow"` or `"deny"` | What the pre-run hook does when the gate itself breaks. `"allow"` fails open and says so. `"deny"` blocks every tool call the gate could not check. Anything else allows, with a notice. |
| `pin_hash_mb` | number | `200` | 0 or more | Megabytes of input files hashed per hook call. Past it, a file is pinned by size and modification time. |
| `pin_seconds` | number | `5` | 0 or more | Seconds the pin check may take. `0` skips hashing. A check cut short lets the run go ahead and names the inputs it did not re-check. |
| `pin_scripts` | boolean | `true` | `true` or `false` | Pin the scripts a plan names, and re-pin with a notice when one is edited. `false` turns this off. Any other value is ignored with a notice (pinning stays on). |
| `lint_before_run` | `false` or string | `false` | `false`, `"warn"`, `"block"` | At a gated run, tell you and the agent (`"warn"`) or deny the run (`"block"`) when a script it uses still has open lint findings recorded at write time. Any other value turns it off, with a notice. |
| `lint_before_stop` | boolean | `false` | `true` or `false` | Block the end of a turn once per change while scripts written this session have open lint findings. Takes effect only when it is exactly `true`, and only while `lint_on_write` is not `false`. |
| `lint_on_write` | boolean | `true` | `true` or `false` | After the agent writes or edits a gated script, lint it and hand the open findings to the agent. Never blocks. Only `false` turns it off. |
| `card_lint` | boolean | `true` | `true` or `false` | Lint the planned code when the approval card is shown. The result is one line on the card and never blocks approval. Only `false` turns it off. |
| `card_coverage` | boolean | `true` | `true` or `false` | Add the `Coverage` row and the `Not established before running` block to the approval card. The card shows it only when the value is exactly `true`; `false`, or any other value, leaves it out. |
| `checkpoint_steps` | whole number | unset (off) | 1 or more; `0` or unset is off | A plan table with more than this many step rows asks one comprehension question before the first `approve`. Any other value is ignored, with a notice. |
| `max_runs_per_approval` | whole number | unset (no limit) | 1 or more | After this many runs under one approval, the next gated run is denied until you approve the plan again. Any other value is ignored, with a notice. |
| `focus_notices` | boolean | `false` | `true` or `false` | At turn end, one line to you when scripts under another analysis ran while a `focus` was open. Takes effect only when it is exactly `true`. |

### Notes on single keys

- **`on_error`.** `"deny"` blocks tool calls only. A broken prompt, post or stop hook reports the error and carries on. A `gate.json` that cannot be read cannot opt in to `"deny"`. Each error is appended to `.mycelium-extra/gate-errors.jsonl` when that file can be written. See [Gate](gate.md#errors-and-on_error).
- **`card_coverage`.** The shipped default changed from off to on in 0.14.0. Add `"card_coverage": false` to get the old card back.
- **`lint_*` keys and `card_lint`.** They call scilintr when it is installed. When scilintr cannot check something, the gate says so and does not report a clean result. Paths of the linters come from `.mycelium-extra/tools.json` when `init --tools` recorded them, else `PATH`.
- **`pin_hash_mb` and verify.** `verify` has its own budgets, `--hash-mb` (default 2000) and `--seconds` (default 120). They are command-line options of `verify`, not keys of `gate.json` ([verify](skills/verify.md)).
- **Friction is opt-in.** `lint_before_run`, `lint_before_stop`, `checkpoint_steps`, `max_runs_per_approval`, `focus_notices` and `on_error: "deny"` are all off or unset by default.

### What the gate itself validates

The gate checks `approval_hours`, `pin_hash_mb`, `pin_seconds` and `on_error` when it loads the file. `pin_scripts`, `lint_before_run`, `max_runs_per_approval` and `checkpoint_steps` give their own notice at the point they apply. The remaining keys are read as written: a boolean key that holds some other value behaves as the "only exactly" notes in the table say, and `gated_paths` and `gated_commands` are not type-checked at load. `init --diagnose` flags every key whose value is invalid under the rules in the table.

## What `init` writes

`init` can set only three keys: `gated_paths` (`--paths`), `gated_commands` (`--commands`) and `approval_hours` (`--hours`). With none of these options the file is `{}`. `--hours` must be positive, although the gate accepts `approval_hours: 0` in a hand-edited file. See [init](skills/init.md).

Two switches are not keys: `hints on` / `hints off` create and remove `.mycelium-extra/hints.json`, and `allow explore` / `stop explore` apply to one session ([Gate](gate.md#typed-commands)).

See also: [Gate](gate.md), [State files](state-files.md), [What the tool does not guarantee](../concepts/not-guaranteed.md).
