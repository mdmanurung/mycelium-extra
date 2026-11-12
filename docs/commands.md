# Commands

Look-up page. For a guided run, start with the [walkthrough](walkthrough.md).

## Typed commands

Send each as the whole message. The gate answers these itself; the agent cannot type them for you. Case is ignored. A hash is the 8 hex characters on a card.

| You type | Meaning |
|---|---|
| `approve` | Approve the plan card shown last. |
| `approve plan <hash>` | Approve an older waiting plan card by hash. |
| `approve amendment <hash>` | Approve an amendment card. |
| `approve freeze <hash>` | Approve a freeze card: the pins become the scripts you reviewed. |
| `approve <number>` | Answer the comprehension question when `checkpoint_steps` is set. |
| `card <hash>` | Show the full card. Add `checks` or `diff` for one part. |
| `freeze <hash>` | Show the freeze card: scripts changed since approval, with diffs. |
| `allow explore` | Allow exploratory runs (prefixed `MYCELIUM_EXTRA_EXPLORE=1`) for this session. |
| `allow explore <hash>` | The same, limited to that plan's analysis paths. |
| `stop explore` | End the explore permission. |
| `gate off`, `gate on` | Switch the whole gate off or on. While off, nothing is checked or recorded. |
| `/goal <condition>` | Claude Code command. The gate pauses itself until the goal ends. |
| `send packet <12-64 hex>` | Consent to send one prepared review packet. |
| `confirm write <8 hex>` | Consent to one pending write, when `confirm_writes` is on. |
| `hints on`, `hints off` | Turn one-line command suggestions on or off. |
| `focus <folder>` | Say which analysis this session works on. Also `focus status` and `focus end`. |
| `where`, `where short`, `where all` | A short card for the focused analysis: aim, where it stands, what to do next. Answered by the gate (the gate must be on; otherwise use `/mycelium-extra:where`); nothing is run. |

Only the exact words count. `approve it` is an ordinary message and approves nothing.

## Skills

Claude Code and OpenCode: `/mycelium-extra:<skill>`. Codex: `$mycelium-extra:<skill>`. Skills marked (you) run only when you call them.

| Skill | What it does |
|---|---|
| `grill` | Turns a task into a sourced, numbered plan and waits for approval. |
| `init` (you) | Turns on the approval gate in this repository. |
| `verify` | Checks what ran against the approved plan; writes provenance after you confirm. Reads runs as the [analysis layout](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/analysis-layout.md) defines them. |
| `plan-review` | Challenges a plan before approval. Nothing leaves the machine without consent. |
| `plot-first` | Makes saved, inspected plots the evidence for each conclusion. |
| `new-analysis` (you) | Scaffolds an analysis folder with stubs (`01_prepare.R`, `02_fit.R`, `03_show.R`), a plot theme, plan, Snakefile and `run.sh`, which writes one overwritten folder per script and a change log in the [analysis layout](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/analysis-layout.md). |
| `analysis-report` (you) | Fills the Quarto report after a run. `analysis-report artifact <folder>` builds a checked, private evaluation page (written to `.mycelium-extra/artifacts/`) for Claude Code; publishing asks first. Reads the run named in the [analysis layout](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/analysis-layout.md). |
| `repo-setup` (you) | Sets up a new analysis repository or Python package. |
| `data-contract-check` | Checks a plan's data assumptions against the sample table, read-only. |
| `decision-status` | Finds which past decision still binds a choice. |
| `manuscript-audit` | Read-only audit of figure and table lineage in a manuscript repository. |
| `track-changes` | Shows what changed against the approved plan, read-only. |
| `focus` (you) | Explains the typed `focus` command. |
| `where` (you) | Shows the "what is going on" card for one analysis; the same words can be typed. |
| `handoff` (you) | Writes a short `HANDOFF.md` so a fresh session can resume; it names `outputs/current` as the [analysis layout](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/analysis-layout.md) defines it. |
| `handoff test` (you) | Has a fresh reader try `HANDOFF.md` or a filled report from a staged copy and lists the gaps. An instruction, not a sandbox. |
| `harden` (you) | Ships one learning's mitigation as a real test. |
| `idea` | Parks an idea in one line. The model can invoke it. |
| `idea-triage` (you) | Ranks parked ideas. |
| `questionnaire` (you) | Turns questions only someone else can answer into a questionnaire. |

## Limits

- The gate reads the words of a shell command. It does not trace `make`, scripts outside `gated_paths`, or MCP notebook tools.
- A script edited after approval is re-pinned with a notice, not blocked.
- While the gate is off, nothing is recorded, so `verify` reports those runs as missing.
- An internal gate error fails open and says so, unless `on_error` is `"deny"`.

## What the gate recorded

:::{figure} figures/scenario/session-timeline.svg
:alt: Timeline of one session in seven events: plan shown, a run denied, plan approved, three runs with receipts, verification.
:width: 90%

Each mark is an event the gate recorded in the walkthrough session: the card shown, a run denied before approval, your approval, three covered runs with their receipts, and the verify check. `verify` reads these records, not the chat.
:::

## Full reference

- [Gate reference](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/gate.md)
- [Skill reference pages](https://github.com/mdmanurung/mycelium-extra/tree/main/docs/reference/skills)
- [Advanced use](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md)
- [Changelog](https://github.com/mdmanurung/mycelium-extra/blob/main/CHANGELOG.md)
