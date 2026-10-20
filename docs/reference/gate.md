# Gate reference

The gate is the part of mycelium-extra that runs as host hooks. It sees your prompts, the agent's tool calls and the end of each turn. It checks covered runs against the plans you approved, answers a few typed commands itself, and writes the records `verify` reads later. It catches execution mistakes and shows gaps. It is not a security boundary: see [What the tool does not guarantee](../concepts/not-guaranteed.md) and [How control works](../concepts/control-model.md).

The gate is off in a repository until `.mycelium-extra/gate.json` exists ([init](skills/init.md), [gate.json](gate-json.md)). Every hook first looks for that file, walking up from the working folder, and returns at once without it.

## Hook events

All hooks start through `hooks/py.sh --hook hooks/gate_run.py <event>`. `py.sh` picks the newest `python3.N` on `PATH` (3.14 down to 3.9), else `python3`; set `MYCELIUM_EXTRA_PYTHON` to name one. The gate needs Python 3.9 or later.

### Claude Code (`hooks/hooks.json`)

| Event | Matcher | Argument | Timeout |
|---|---|---|---|
| `UserPromptSubmit` | none | `prompt` | 10 s |
| `PreToolUse` | `Bash\|Write\|Edit\|MultiEdit\|NotebookEdit` | `tool` | 10 s |
| `PostToolUse` | `Bash` | `post` | 20 s |
| `PostToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit` | `post` | 20 s |
| `PostToolUseFailure` | `Bash` | `post` | 20 s |
| `Stop` | none | `stop` | 30 s |

### Codex (`hooks/codex.json`)

The same events with `--host codex`, except that there is no `PostToolUseFailure`. Tool matchers are `Bash|apply_patch` for `PreToolUse`, and `Bash` and `apply_patch` as two `PostToolUse` entries. Timeouts are the same as above. Codex needs enabled and trusted hooks, and CLI 0.160.0 or later. In 0.160.0 the post hook gives no exit status, so every Codex receipt records exit status `unknown` and `verify` reports a gap. A failed `Bash` or `apply_patch` call therefore never reads as a pass: when Codex sends the post event it is receipted `unknown`, and when it sends none the planned step has no receipt at all. Neither is recorded as a completed run (Claude Code, which does send `PostToolUseFailure`, records the exit code when the message carries one).

### OpenCode (`opencode/index.js`)

A plugin adapter, not a hooks file. It is loaded through the `plugins` setting ([Installation](../installation.md)), maps OpenCode's own events onto the same gate (`gate_run.py --host opencode`), and is inert in a repository with no `.mycelium-extra/gate.json`.

| OpenCode | Gate event |
|---|---|
| `shell`, `write`, `edit`, `patch` tool, before execution | `PreToolUse` as `Bash`, `Write`, `Edit`, `apply_patch` (10 s) |
| the same tools, after execution | `PostToolUse` (20 s); a failed call becomes `PostToolUseFailure`; the shell result's `metadata.exit` becomes the exit code |
| session prompt | `UserPromptSubmit` (10 s) |
| end of a turn (`session.execution.succeeded`, `.failed`, `.interrupted`, or `session.idle`) | `Stop` (30 s), on the last assistant text |

Differences you will see on OpenCode: a deny is a thrown error; a notice is appended to the tool result or posted as a synthetic session message; a blocked prompt (a card, `focus status`) is shown to you directly and the agent's copy of the prompt is replaced by the reply, so the card reaches you through the session. A `Stop` block becomes a steering prompt. The adapter keeps only events from its own folder, because the OpenCode event stream is shared across locations. Qualified on OpenCode 2.0.32.

### Not registered on any host

`SessionStart`, `SessionEnd`, `PreCompact` and subagent events. mycelium-extra prints nothing at session start by design.

## Typed commands

Send each as the whole prompt. The hook answers these itself; the agent does not run them and cannot type them for you. Case is ignored and one trailing `.` or `!` is allowed. A hash is the first 8 hex characters shown on a card.

| You type | What the hook does | Writes |
|---|---|---|
| `approve plan <hash>` | Approves a plan card. | `approvals/<hash>.json`, `approval-instances/<hash>/<id>.json`, one line in `approvals.jsonl` |
| `approve amendment <hash>` | Approves an amendment card. | same |
| `approve freeze <hash>` | Approves a freeze card; the pins become the scripts you reviewed. | same |
| `approve <hash>` or `approve plan` / `approve` with no hash | Plain `approve <hash>` works on any card. With no hash it works only when exactly one card is waiting and it is the one shown last; otherwise nothing is approved and the reply lists the pending hashes. | same |
| `approve plan <hash> <number>` | Answers the comprehension question when `checkpoint_steps` is set. Not an approval when it is unset. | same, on a right answer |
| `card <hash> checks`, `card <hash> diff`, `card <hash> full` | Shows the rest of a card. `card <hash>` alone means `full`. | nothing |
| `freeze <hash>` | Shows the freeze card: scripts changed since the approval, with diffs, the steps to re-run, runs so far and gaps now. | a pending freeze entry in `pending/` |
| `hints on`, `hints off` | Turns one-line command suggestions on or off for the repository. | creates or removes `hints.json` |
| `allow explore` | Session-wide permission for runs prefixed `MYCELIUM_EXTRA_EXPLORE=1`. | `explore-grants/<session>.json` |
| `allow explore <hash>` | The same, bounded to that approved plan's analysis paths and protected files. | same, with a scope |
| `stop explore` | Ends the explore permission. | removes the grant |
| `send packet <12-64 hex>` | Records your consent to send one prepared review packet. The whole prompt must be this line. | `review-consent/<digest>.json` |
| `focus <folder>`, `focus <folder> plan <hash>`, `focus switch <folder>`, `focus status`, `focus end` | Declares which analysis this session is working on. See [focus](skills/focus.md). | `focus/<session>.json` |

Rules that matter:

- Only the exact words count. `approve it` or `ok, approve` is an ordinary prompt. A prompt under 200 characters that contains `approve plan`, `approve amendment` or `approve freeze` but is not the exact command gets a reply that nothing was approved.
- Each verb works only on its own kind of card. Using the wrong verb approves nothing and the reply names the right one. Plain `approve <hash>` works on any card.
- A hash can be approved only once its pins and card are prepared. A hash still marked `(preparing)` or `(invalid block)` in the pending list is refused.
- An approval is restricted to the session that showed the plan. A pending hash from another session grants nothing; show the plan again in the new session.
- `card` and `freeze` replies are shown to you only. On Claude Code the agent never sees them.
- Approval is the only way a plan gets authority. Text an agent writes, or text that arrives inside a tool result or a web page, cannot approve anything: approval exists only for a user prompt that matches the command.

## Decisions

Each hook returns one of a few kinds of answer.

### UserPromptSubmit

| Answer | When |
|---|---|
| Blocked with a reason (shown to you, hidden from the agent) | `card`, `freeze`, `focus status`, and a refused `focus` command |
| Notice to you and the agent | an approval was recorded or refused, `hints on|off`, an explore grant, a recorded packet consent, a `focus` change, a failed comprehension question, `approve` with nothing or too many waiting |
| One-line command hint | only after `hints on`, on a prompt that matches a task type |
| Silence | every other prompt |

While a focus is open, one advisory line is added to a prompt's context.

### PreToolUse (can deny)

| Answer | When |
|---|---|
| **Deny** | a Write, Edit, `apply_patch` or Bash write into `.mycelium-extra/`; a gated run that no active approval covers; the explore prefix without `allow explore`; a scoped explore run outside the plan's analysis paths; a pinned input changed since the plan was shown; a pinned validation or exact-execution file changed, or a run that differs from a frozen step; the `max_runs_per_approval` limit reached; `lint_before_run: "block"` with open findings; reading `approvals/` took longer than 5 s; a malformed approval record or script-pin ledger; a gate error with `on_error: "deny"` |
| **Allow with a notice** | a script the plan lists was edited (re-pinned, with the lines and numbers that moved); pinned inputs not re-checked because of the time limit; a first-run script pin; a scoped explore run, or an edit of a protected test file under a scoped grant; `lint_before_run: "warn"` with open findings; an invalid `gate.json` value |
| **Silent allow** | everything else. The gate never auto-approves a tool call, so your host's own permission prompts still apply. |

Reading gated files (`cat`, `rg`, `git`) is never gated. A deny is logged in `denies.jsonl`. A run that is denied leaves no receipt.

### PostToolUse and PostToolUseFailure (never block)

| Answer | When |
|---|---|
| Receipt written | after a covered shell call: one line per run in `receipts.jsonl` |
| Notice to the agent | in a repository with `.living/`, once, that Mycelium's post-action protocol did not fire for a run it cannot see (`bash run.sh`, snakemake, sbatch, nextflow); after an explore run, that it is not reportable |
| Lint findings to the agent | after a gated script is written or edited, once per change (`lint_on_write`) |

### Stop

| Answer | When |
|---|---|
| Approval card shown to you | the last reply ends with `Plan status: READY` or `Plan status: READY_WITH_ASSUMPTIONS`. `DECISION_REQUIRED` shows no card. |
| Line to you | explore runs this session that are not reportable; scripts with open lint findings; hints (`verify <hash>`, `handoff` after about 120k tokens of context); with `focus_notices`, another analysis ran under the open focus |
| Block | only with `lint_before_stop: true`, once per change, when written scripts still have open findings |

### Errors and `on_error`

If the gate itself breaks, or cannot be loaded, the hook fails open and prints a message, unless `gate.json` sets `"on_error": "deny"`: then every PreToolUse call it could not check is denied. Prompt, post and stop hooks report the error and carry on. Each error is appended to `gate-errors.jsonl` with its event, decision, host, session and call id when they can be decoded. A hook running on Python older than 3.9 first hands the event to `py.sh` once, and only then reports "needs Python 3.9 or later" and follows `on_error`.

## Forms the gate does not trace

These are listed so you know where a run can happen with no denial and no receipt. `verify` reports such a run only when it can see its outputs.

- Not traced: `make` and other build tools outside `gated_commands`; `bash script.sh` or `./run.sh` outside `gated_paths` (what a script runs inside is not read); `runpy`, `ipython`, `pypy`; `xargs python3`; `find -exec`; `eval` of a variable; a script written in an earlier call and then run.
- Unresolved, therefore denied unless a plan covers the literal text: a runner whose script is a shell expansion (`python3 $f`, `python3 $(ls ...)`, a loop variable, a variable set earlier), and a `cd` or `pushd` into one. Write script paths literally.
- Tools other than Bash and the file-edit tools are not gated. Code run through an MCP notebook tool (`nb_*_execute`) or any other tool the gate does not match bypasses both the gate and the lineage.
- State-folder protection is partial. Write and Edit paths, `rm -r*`, `mv`, `cp`, `tee`, `sed -i`, redirects, `find -delete` (with no `-name` or `-path` test), `rsync --delete`, `git clean -x`/`-X` and `git stash -a` are denied. Not seen: `git clean -fd` or `git stash -u` while the folder is untracked and not ignored, a script that deletes it, and a variable or glob the gate cannot resolve. A repository whose `gate.json` is gone is ungated and says nothing; `verify` then reports the plan's runs as unrecorded, a gap and never a clean pass.
- Edits to a script a plan lists are re-pinned with a notice, not blocked, so a covered run can execute code newer than the code you approved. `freeze` and `verify` show what changed.
- Size-and-mtime and folder fingerprints miss an edit that keeps both (for example `cp -p`).
- A receipt records the environment a job declares, not the one it resolved. A job ID records a submission, not its outcome.
- An exit status is inferred from which hook event fired; on Codex it is `unknown`.
- An agent set on bypassing the gate through Bash can do so.

Full detail for each item, with the pinning, receipt and explore rules, is in [Approval gate](../approval-gate.md) and [Advanced features](../advanced.md). Settings are in [gate.json](gate-json.md); files are in [State files](state-files.md). Guides: [Approve and run](../guides/approve-and-run.md), [Amend, freeze, re-scope](../guides/amend-freeze-rescope.md).
