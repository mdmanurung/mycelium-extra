# E11. A handoff that saved the next session

Control point: **reversibility**

Anonymised from a real project. Source: the HANDOFF.md files of projects A and B (both dated the same day).

## 1. Socratic: ask these first

- If this conversation ended now, what would the next session have to rediscover?
- Which decisions did I lock, and which things must not be redone?
- Which approval expires, and what happens to a pending plan if the context is cleared?

## 2. What the handoff carried (excerpts, anonymised)

```text
## Next action
When the batch finishes (check the scheduler), present a plan naming the three steps below and get
`approve plan <hash>` in that session (the earlier plan covered them but expires after 24 h), then ...

## Locked decisions
- Reading rule fixed before the result (user): a refit passes if <ratio> at every later visit; refits failing
  the sampler gate are not read, not rerun.
- Refits are diagnostic; the primary wave keeps the plan's priors; any model change is the user's decision.

## Dead ends - do not redo
- Editing a script while its batch job runs: the interpreter reads the file lazily. Copy to a new name.
- Editing a gated script after its first run without re-approval: the gate pins it.
- `/clear` drops pending plans: `approve plan <hash>` only works in the session that presented it.

## Read first
- <findings file> entry <id> has a WRONG phrase; correct it with step 6 (wording only).
```

## 3. Track-changes shape

Observed: the file states a wrong phrase and names the step that corrects it. Gap: the correction was not yet made. Unknown: whether the plan's 24 h window will still be open.

## 4. Librarian block

None.

## 5. What the human decided

Start the next session by presenting a fresh plan and typing the approval there, not by trusting an expired one; keep the reading rule as written.

## 6. Without it

The next session would re-run a dead end, wait on an approval that never carries over, or choose the reading rule after seeing the result.

Basis: 2 handoffs (project A, project B); the handoff skill overwrites the previous one by design.
