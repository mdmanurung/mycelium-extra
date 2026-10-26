# focus

Records which analysis one session is working on. Advisory: it grants no run, extends no approval and pins nothing. Guide: [Stay oriented](../../guides/stay-oriented.md).

## Synopsis

You type this skill; the agent does not start it on its own (`disable-model-invocation: true`, and Codex's `allow_implicit_invocation: false`).

You type the commands; the gate answers them before the agent sees them. The skill (`/mycelium-extra:focus`) only explains and lists folders:

```bash
sh <skill-dir>/../../hooks/py.sh - list [--repo DIR] < <skill-dir>/../../hooks/focus.py
```

## Typed commands

Send each as the whole prompt. A focus belongs to one session and is never restored in a new one.

| You type | Meaning |
|---|---|
| `focus analysis/X` or `focus nbs/topic` | Start a focus on an existing folder under a gated root (`analysis/`, `nbs/`, or the roots of `gated_paths`). Refused if one is already open, the folder does not exist or is outside those roots. |
| `focus <folder> plan <hash>` | The same, and notes that approved plan `<hash>` states the original intent. Refused unless that plan's table names a path inside the folder. |
| `focus status` | A short card: objective (quoted from the analysis doc), plan, and whether a run is authorised in this session. |
| `focus switch <folder>` | Ends this focus and starts the next; the first stays in the record. |
| `focus end` | Closes it. It does not mean the analysis is done or reportable. |

## Reads and writes

Reads `gate.json` (for `gated_paths`), approvals, and the analysis doc. Writes `.mycelium-extra/focus/<session>.json` (`mycelium-extra.focus.v1`) and a lock under `locks/`, only on your typed command. A host that sends no session id gets "no focus change". While a focus is open, one advisory line is added to each prompt's context, and receipts of runs launched under it carry `focus_id` and `focus_folder`.

## Default on or off

Off until you type `focus <folder>`. Related setting: `focus_notices` (default `false`) adds one line at turn end when scripts under another analysis ran during the focus ([gate.json](../gate-json.md)).

## Enforced versus the agent's instruction

| Step | Kind |
|---|---|
| Only your typed command changes a focus | Enforced: the gate denies the agent's writes into `.mycelium-extra/`, and no script exists for it to call |
| A focus is not permission; a run still needs an approved plan | Enforced: the gate does not read focus when deciding a run |
| Staying on the focused analysis, and offering `focus switch` for off-topic requests | The agent's instruction |

See [track-changes](track-changes.md) to review what changed against the approved intent, and [new-analysis](new-analysis.md) for a folder that does not exist yet.
