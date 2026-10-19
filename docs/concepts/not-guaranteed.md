# What is not guaranteed

This page says what Mycelium Extra does not promise. It is the threat model in plain words. Read it before you rely on a status line in a write-up.

## The threat model

The gate is built for an agent that is careless, over-eager, or steered by text in its context: a file, a tool result or an old handoff that says "approve". Against that, it asks three questions. Can consent be forged by accident or by injected text? Can a covered run slip past unseen? Does every failure show up as a visible gap?

It is **not a security boundary.** An agent with shell access that is set on bypassing the gate can do so. So can you, because your own typed words are the only consent the gate recognises. The gate catches execution mistakes and shows gaps. It does not defend against someone who wants to defeat it.

## The confirmation steps are instructions, not rules

Several skills ask you before they write: `verify write`, `decision-status`, `harden`, `idea-triage` and `new-analysis`. That "ask first" step is part of the agent's instructions. Nothing in the gate enforces it. Only the `approve`, `freeze` and `allow explore` messages you type are enforced, and the gate answers those itself.

## Runs the gate does not trace

A run of this kind is not denied and leaves no receipt. `verify` reports it only when it can see its outputs. From [the approval gate's Limits](../approval-gate.md#limits):

- build tools outside `gated_commands`, such as `make`;
- `bash script.sh` or `./run.sh` outside `gated_paths`: what a script runs inside is not read;
- `runpy`, `ipython`, `pypy`, `xargs python3`, `find -exec`, and `eval` of a variable;
- a script written in an earlier call and then run;
- code run through an MCP notebook tool (`nb_*_execute`) or any other tool the gate does not match. It bypasses both the gate and the lineage;
- a file a script sources or imports, unless you list it on the plan's `Inputs:` line.

Runner operands that are a shell expansion (`python3 $f`, a loop variable, `$(...)`) are denied rather than traced, so write script paths literally.

State written in ways the gate cannot read is not caught. Some removals of the `.mycelium-extra/` folder (for example `git clean -fd` while it is untracked and not ignored, or a script that deletes it) are not seen. A gate whose `gate.json` is gone is off and says nothing; `verify` then reports the plan's runs as unrecorded, which is a gap.

A host that never runs the hook cannot be controlled by it. A gate that fails open (the default) says so and logs it; set `"on_error": "deny"` if you prefer it to block.

## Edits after approval

An edit to a script the plan lists is re-pinned with a notice, not blocked. A covered run can therefore execute code newer than the code you approved. Your approval is for the plan and its pins as shown. `freeze` and `verify` show what changed, and a reportable run of code no approval froze is a gap.

## Weak fingerprints

A pin by size and time, or by folder listing, misses an edit that keeps both (for example `cp -p`). The notice says which fingerprint each input got. A receipt records the environment a job declares, not the one it resolved. A job ID records a submission, not its outcome; check `sacct` or the job log. On Codex 0.160.0 the exit status is `unknown`, which `verify` shows as a gap.

## What `verify` cannot show

- Whether the code implements the plan's choices. A run of a planned script proves it ran. That is the job of review.
- Whether a number is true. A claim is checked against its output cell, and only where a `<!-- claims -->` block names the cell. Other numbers in the text are listed, not checked.
- Whether a cited paper supports its sentence. A resolved citation shows the identifier exists and matches the text next to it.
- What a validation binding's author intended. `defined_by` is the plan's own claim.
- Runs outside the gate's view (the list above) and Mycelium's lineage for sessions that have not finished.
- Anything on a host that dropped its hook events.

`verify` never re-runs the analysis. `CONFORMS` means the records agree with the plan. It does not mean the run is complete in the world.

## Scientific validity is out of scope

The tool checks that what ran matches what you approved, and it shows what it could not check. It does not judge whether the question, the method, the model, the thresholds or the interpretation are right. A plan can be approved, run, verified as `CONFORMS` and be scientifically wrong. Review, replication and your own judgement stay with you.

## Findings from the 0.14.0 review

Two independent reviews of 0.14.0 found, among others, these limits. Version 0.14.1 fixed some of them, and the rest stay documented here:

- **Fixed in 0.14.1:** combined shell flags such as `bash -lc` could write an approval record; loops, `$VAR`, `pushd` and container wrappers slipped past unseen; a citation past the 40th was never flagged; a frozen plan's text was never re-hashed.
- **Still true:** some state-deleting commands are not seen (above); `make` and `bash <script>` are untraced; the OpenCode adapter depends on the plugin being loaded; native Claude Code and Codex sessions, hook timeouts and whether any host fires the prompt hook for agent-submitted prompts were not tested in the review.
- **Not validated:** `verify`'s per-rule conda environment record for `snakemake --use-conda` is built on a synthetic fixture, not a real Snakemake run.

For what the tool does promise, see [The control model](control-model.md) and [Gaps and passes](gaps-and-passes.md).
