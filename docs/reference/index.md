# Reference

One page per skill, then the pages about the gate, its settings and its files. Each entry states what the code does at this version. For how to do a task, use the guides. For why the tool is built this way, use the concepts pages.

## Skills

Every skill is a slash command in Claude Code (`/mycelium-extra:<name>`), a `$` command in Codex (`$mycelium-extra:<name>`) and a `/` command in OpenCode. The scripts behind them run from stdin through `hooks/py.sh`, never by path, so Mycelium's own hooks stay closed.

| Skill | One line | Writes |
|---|---|---|
| [init](skills/init.md) | Turn the approval gate on in a repository | `.mycelium-extra/gate.json`, `.gitignore` |
| [grill](skills/grill.md) | Turn a task into a sourced plan and stop for your approval | nothing |
| [data-contract-check](skills/data-contract-check.md) | Test a plan's data assumptions against the sample table | nothing by default |
| [manuscript-audit](skills/manuscript-audit.md) | Read-only audit of manuscript figure/table lineage and source data | nothing by default |
| [decision-status](skills/decision-status.md) | Work out which past decision still binds | one `.living/decisions.md` entry, after you confirm |
| [verify](skills/verify.md) | Check what ran against the approved plan; record provenance | `provenance/` on `write` |
| [track-changes](skills/track-changes.md) | Show what changed in one analysis since its approved plan | `.mycelium-extra/track-changes/` |
| [focus](skills/focus.md) | Say which analysis this session is working on | `.mycelium-extra/focus/` (your typed command only) |
| [plan-review](skills/plan-review.md) | Independent review of a plan before you approve it | `.mycelium-extra/review-packets/` |
| [new-analysis](skills/new-analysis.md) | Scaffold an analysis folder | the new folder |
| [plot-first](../../skills/plot-first/SKILL.md) | Tie analysis conclusions to inspected plots | figures and analysis docs within approved work |
| [idea](skills/idea.md) | Park an idea in one line | `todo/` |
| [idea-triage](skills/idea-triage.md) | Rank parked ideas so you can choose | `todo/` annotations, after you pick |
| [handoff](skills/handoff.md) | Write `HANDOFF.md` for a fresh session | `HANDOFF.md` |
| [harden](skills/harden.md) | Ship a learning's check as a test | a test file and one `.living/learnings.md` entry, after you confirm |

## Gate and files

| Page | What it covers |
|---|---|
| [Gate](gate.md) | hook events on each host, typed commands, every allow, deny and notice, what the gate does not trace |
| [gate.json](gate-json.md) | all 15 settings with default, type and validation |
| [State files](state-files.md) | every file under `.mycelium-extra/` and `provenance/`, who writes and reads it, and the proposed 1.x compatibility surface |

## Reading the "confirmation" lines

Many skills ask you before they write. On each page, a step is labelled one of two ways:

- **Enforced by the gate or the script.** A hook or script does it regardless of what the agent decides. Examples: only your typed `approve plan <hash>` creates an approval; `init` never overwrites an existing `gate.json`; `review_packet.py verify` refuses when its consent record does not match.
- **The agent's instruction.** The skill tells the agent to ask first, but nothing stops it from running the command. Examples: asking before `verify write`, before appending to `.living/decisions.md`, before editing a learning. Check what the agent did; do not rely on the prompt.

See [How control works](../concepts/control-model.md), [Gaps and passes](../concepts/gaps-and-passes.md) and [What the tool does not guarantee](../concepts/not-guaranteed.md).

## Guides by task

[Plan an analysis](../guides/plan-an-analysis.md) · [Approve and run](../guides/approve-and-run.md) · [Verify and record provenance](../guides/verify-and-provenance.md) · [Amend, freeze, re-scope](../guides/amend-freeze-rescope.md) · [Stay oriented](../guides/stay-oriented.md) · [Hand off](../guides/hand-off.md) · [Second-model review](../guides/second-model-review.md) · [Harden against repeats](../guides/harden-against-repeats.md) · [With Mycelium or in a plain repo](../guides/with-mycelium-or-plain-repo.md)
