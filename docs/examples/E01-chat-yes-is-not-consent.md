# E01. A chat "yes" is not an approval

Control point: **consent**

Anonymised from a real project. Source: the approved plan text of the first session of project A (the agent's own account of the block). That project had no `denies.jsonl`, so the deny itself is quoted from a regenerated run on the synthetic fixture, not from a record.

## 1. Socratic: ask these first

- What exactly did I say yes to: the work, or a specific plan the gate can hash?
- Which words does the gate accept as my approval, and did I type them?
- If the agent had run the script anyway, what record would show it?

## 2. What happened

The researcher agreed in chat to scaffold a new analysis folder. The agent tried a dry run of the scaffold script, and the PreToolUse hook denied it before anything was written:

```text
mycelium-extra gate: blocked because no active approved plan covers this run.
  - python3 analysis/example/scripts/01_prepare.py
Active approved plans (last 24 h): none.
Present a plan whose plan table names these paths (prose, Evidence, and Source citations do not count) and that ends with the grill status line; the user approves it by typing `approve plan <hash>`. Do not work around this block; if the user wants an exploratory run instead, they will say so.
```

The researcher's plain "yes, go ahead" produced no approval (the prompt hook returns nothing for it). The agent then wrote, in the recorded plan: "I was wrong when I said chat approval alone would satisfy this gate." It presented a corrected three-step plan whose Step column named the scaffold script, and the researcher typed `approve plan <hash>`.

## 3. Track-changes shape

Not a change episode: no plan, script or input had changed yet, so there is nothing to show. Observed: one denied run, zero files written. Unknown: whether the agent tried other routes (shell-made writes are not observed).

## 4. Librarian block

Not a grill episode with a methodological question; none.

## 5. What the human decided

Approve the corrected plan by its hash. The agreement in chat stayed an intention, not a grant.

## 6. Without the tool

The agent would have run the scaffold on a conversational yes. Nothing would show afterwards which words authorised it.

Basis: 1 session, 2 plans approved in it, 0 denies on file (project has no `denies.jsonl`).
