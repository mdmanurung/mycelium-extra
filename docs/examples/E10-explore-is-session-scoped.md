# E10. Exploring without a plan: opt-in, per session, logged, never a result

Control point: **override**

Anonymised from a real project. Source: project A's `explore.log`, `explore-grants/` and receipts (12 explore runs, 3 grants, 367 gated runs), and the handoff line "explore is allowed this session only; a new session needs `allow explore` again; a smoke run is not a result, do not quote its estimates". Notices regenerated on the fixture.

![Session A has an explicit explore grant and logged nonreportable attempts. Session B inherits no grant. Reporting requires a normal approved rerun rather than promotion of an exploratory output.](../figures/session-exploration.svg)

This schematic distinguishes sessions, not elapsed time or productivity. An exploratory output does not become reportable; plan and approve a normal rerun.

## 1. Socratic: ask these first

- Do I want this try to be reportable? If not, who says so, and where is it recorded?
- Does the grant last beyond this conversation?
- If a number from a try ends up in a document, what flags it?

## 2. What the tool showed

Without the grant:

```text
mycelium-extra gate: the exploratory-run prefix works only after the user types `allow explore` in this session, and they have not. Do not work around this block; ask the user.
```

After the researcher types `allow explore`:

```text
mycelium-extra: exploratory runs allowed for this session. Prefix a gated run with MYCELIUM_EXTRA_EXPLORE=1; each one is logged and listed as not reportable. ... `stop explore` ends this.
```

After each try, the agent is told: "that was an exploratory run, not reportable ... label it `Exploratory run (not reportable)`". `verify explore` lists it with the code's hash and "session-wide grant (not tied to a plan)", and says an explore run never validates a check or owns an output.

## 3. Track-changes shape

Observed: runs under an explore grant, with the code version each used. Potential: a smoke run's estimates leaking into notes. Gap: promotion needs an approved rerun. Unknown: inline-code tries (not recorded).

## 4. Librarian block

None.

## 5. What the human decided

Allowed exploration for one session to smoke-test a script on a small input, then planned the real run; the handoff told the next session the smoke output was not a result.

## 6. Without the tool

A quick try and a reportable run would be indistinguishable in the record.

Basis: 12 explore runs, 3 sessions, 3 grants, 367 gated runs (project A); project B had 0 explore runs.
