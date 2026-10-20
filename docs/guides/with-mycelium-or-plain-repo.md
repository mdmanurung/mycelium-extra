# With Mycelium, or in a plain repository

Mycelium Extra works in both. With Mycelium it reads the project's records; without, it starts from your README, docs, tests, config and code.

## What you control here

- **Your typed word:** the same approvals in both cases. Mycelium never approves anything for Extra, and Extra never approves for Mycelium.
- **Shown to you:** where the plan's evidence came from (`repo: <path>`), and what the install can see (`init --diagnose`).
- **To say no:** Extra never writes `.living/` or Mycelium's manifests, except three confirmed or by-design writes: `decision-status` appends a resolution, `harden` edits one learning, and `idea` and `idea-triage` write under `todo/`. The details are in [Mycelium integration](../mycelium-integration.md#boundaries). Turn the gate off by removing `.mycelium-extra/gate.json`.

## Steps

1. **Detect.** A repository uses Mycelium when `.living/` exists. Partial structure is normal, and missing manifests, index or findings are treated as normal.
2. **Check the install.** Read-only, writes nothing:

   ```text
   /mycelium-extra:init
   ```

   run with its `--diagnose` option reports the effective config, hook registrations, the Mycelium version, and which optional tools are present. A registration does not prove the host trusts the hooks; check `/hooks` and restart.
3. **Plan.** In a Mycelium repository `grill` reads decisions, findings and conventions first. In a plain repository it reads the README, docs, tests, config and code.
4. **Run.** Use Mycelium's `analyze` (`/mycelium:analyze` in Claude Code, `$mycelium:analyze` in Codex), or your own workflow in a plain repository. The gate applies either way.
5. **Review before the freeze.** Use Mycelium's `review`, or your own. Extra does not check that a review happened.
6. **Record.** `verify write` saves provenance in the analysis folder. In Mycelium, record the verify status and the plan's "Decisions to record" through Mycelium's normal logging.

| Task | Mycelium | Plain repository |
|---|---|---|
| Decisions and learnings | `.living/decisions.md`, `learnings.md` | `decision-status` and `harden` say so and stop |
| Plan sources | `.living/`, manifests, findings | README, docs, code |
| Data lineage | Extra's `verify` reads it for gaps | none, no message |
| Implement, review, report | `mycelium:analyze`, `review`, `report` | your own tools |

## Worked example

Real output of `init --diagnose` from the harness fixture project, which is not a Mycelium install (paths shortened, synthetic project). The Mycelium and hooks lines show what a missing piece looks like:

```text
mycelium-extra diagnose (read-only; nothing was written)
gate: on, from <project>/.mycelium-extra/gate.json
hooks: plugin root not found (/); pass --plugin-root DIR, the folder holding hooks/.
mycelium: none found here (no .mycelium/plugin-root); mycelium-extra works without it.
last observed:
  no run receipt recorded yet.
  no gate error recorded.
note: a hook registered in a manifest, or a gate.json in the repository, does not prove the host has enabled or trusted the hooks. Check /hooks in Codex or Claude Code, and restart the session.
```

The `hooks:` line appeared because the harness did not pass `--plugin-root`; do so if yours says the same.

## What this does not guarantee

Extra's reads of Mycelium are tested against the versions named on [Mycelium integration](../mycelium-integration.md); another version prints a note and is not otherwise checked. Mycelium's lineage covers finished sessions only. See [what this does not guarantee](../concepts/not-guaranteed.md).

## Reference

[init](../reference/skills/init.md) · [grill](../reference/skills/grill.md) · [Mycelium integration, in full](../mycelium-integration.md) · [gate](../reference/gate.md)
