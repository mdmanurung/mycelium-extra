# The control model

Mycelium Extra is built around one question: does every function leave you, the researcher, in control of what is planned, what runs, what is recorded, and what is claimed? This page turns that question into seven plain promises. Each one says what the tool does and shows where you meet it. The reviews before a release score every function against the same seven.

The promises describe how the tool behaves when everything works. They do not turn it into a lock. See [What is not guaranteed](not-guaranteed.md) for what they leave out.

![Consent, visibility, honesty, override, reversibility, boundary and attention name the control principles. They describe cooperative behavior, not an enforced security perimeter.](../figures/control-points.svg)

Read each principle with its concrete limits below. Some confirmations are instructions to the agent; these principles are not a security perimeter.

## 1. Consent

**Nothing that runs, writes or records happens until you say so in your own words.**

Approval is a message you type: `approve plan <hash>`, `approve amendment <hash>` or `approve freeze <hash>`. The gate reads only the exact words, and only when the whole prompt is that sentence. Text in a file, a tool result or `HANDOFF.md` that happens to contain the same words approves nothing. The agent cannot write an approval record either: the gate denies its writes into `.mycelium-extra/`.

Example: the agent tries `python3 analysis/vaccine-response/scripts/01_select_samples.py` before any approval. The gate blocks it and says no active approved plan covers the run. The plan is shown to you, and the run starts only after you type `approve plan 84bb5fce`. See [A worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md).

The skills that write something outside the gate (`verify write`, `decision-status`, `harden`, `idea-triage`, `new-analysis`) ask you first. That step is the agent's instruction, not a gate rule.

## 2. Visibility

**Before something happens you see in plain text what it will be, and afterwards you can read what happened without special tools.**

The approval card puts the question, each choice and who made it (`[you]`, `[repo: ...]` or `[default: reason]*`), the checks and what the plan lets run in front of you before you type `approve`. `card <hash> full` shows the rest. After runs, each gated command leaves a receipt, and `verify` prints a report in Markdown. Notices are plain text, never icons you must decode.

Example: a script you approved is edited. The next run is not blocked, but the gate says so with a re-pin notice and the size of the change. `freeze <hash>` shows the diff before a reportable run.

## 3. Honesty

**A gap is never shown as clean.**

If a check could not run, timed out, could not be parsed or was cut short, the tool says so and does not count it as a pass. `verify` ends with `CONFORMS`, `CONFORMS_WITH_GAPS` or `DOES_NOT_CONFORM`, and a missing check can never produce plain `CONFORMS`. The tool also keeps numbers an agent wrote out of the record unless they are tied to an output cell, and it never loosens a contract or threshold to make a check pass. Read [Gaps and passes](gaps-and-passes.md) for how to read a status.

Example: a citation is checked offline. The tool cannot reach a service, so the citation is reported as "not checked (offline)", a gap, and the plan reads `CONFORMS_WITH_GAPS` until you resolve it or say in the write-up that it was not machine-checked.

## 4. Override

**You can always refuse, amend, re-scope or switch a feature off, in a short documented way.**

- Refuse: do not type `approve`. The covered run stays blocked.
- Amend: a plan that only adds to an earlier approval gets a change-only card, `approve amendment <hash>`.
- Re-scope: `focus switch <folder>` and `focus end` change which analysis a session works on.
- Switch off: `hints off` stops command hints; `"card_coverage": false` and `"card_lint": false` in `gate.json` remove the Coverage row and the lint line from the card; `on_error` chooses whether a gate failure blocks. New friction is opt-in.

Example: `focus_notices` is off by default. You turn it on with `"focus_notices": true` in `gate.json` and off by deleting the key.

## 5. Reversibility

**Nothing is overwritten or deleted without showing you the target, and the state can be inspected and undone by hand.**

The gate's state is plain files in `.mycelium-extra/`, listed under [State files](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/state-files.md), and verified provenance is a folder of files under `provenance/`. Approvals are never deleted. `handoff` shows the head of the old `HANDOFF.md` before replacing it, and `harden` writes its test only after you confirm.

Example: to go back after a wrong approval, show and approve a corrected plan; the earlier approval stays on disk as history.

## 6. Boundary

**The tool stays out of Mycelium's files and does not add noise to your session.**

It writes into `.living/` only when you confirm: `decision-status` appends a resolution and `harden` edits one learning. `idea` and `idea-triage` write under `todo/`. These confirmations are the agent's instruction, not a gate rule. It prints no SessionStart messages, because they would compete with Mycelium's session resume. Hooks use only the Python standard library, so there is nothing to install beside the plugin. See [Mycelium integration](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/mycelium-integration.md).

Example: `new-analysis` writes only inside the folder it creates; Mycelium's `analyze` handles manifest and memory updates.

## 7. Attention

**The tool puts one sourced decision in front of you and does not bury it in noise.**

The approval card is short so you can read it before typing. `grill` asks at most five questions after your opening question, and only ones you own. Defaults are starred and listed as "Defaults to confirm". Optional probes (`socratic`, `explain row N`, `challenge row N`) do not count toward the five questions and cannot approve anything. The rubber stamp is the failure to avoid: a card nobody reads is worse than no card.

Example: step 3 of a plan took its threshold from a default. The card marks `[default: matches step 2]*` and adds `Defaults to confirm: step 3`, so the one choice you did not make is the one you are asked about.
