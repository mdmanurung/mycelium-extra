# Codex engineering review

In Claude Code, invoke a fresh Codex task with the current repository as working root and the canonical packet on stdin. Use the installed CLI's read-only sandbox and ephemeral session, for example:

```bash
codex exec --sandbox read-only --ephemeral --ignore-user-config -C <repository-root> -
```

`--ignore-user-config` skips `~/.codex/config.toml`, so no plugins or hooks load (authentication still works). In a repository with `.living/`, Mycelium's Codex hooks otherwise run in the reviewer session and add session-resume and audit instructions that are not part of the packet. If the user's Codex setup needs its config (for example a custom provider), drop the flag and say so in the reviewer status.

Do not use a write sandbox, `--dangerously-bypass-approvals-and-sandbox`, or a Codex implementation worker. Inspect the CLI help for the installed version before using flags. If the CLI, authentication, a usage limit, the sandbox, or project hooks prevent a read-only run, report Codex unavailable: an `ERROR:` line or a reply without the response format is never a clean review. Check the target repository's tracked and relevant ignored state before and after the review; unexpected changes invalidate the read-only claim.

Give Codex the packet and this role:

> Review implementation feasibility, repository compatibility, dependency order, available APIs, data flow and leakage, reproducibility, testability, failure handling, validation, and plan-to-code divergence. Do not redesign the scientific question, edit files, run project scripts, or approve the plan. Cite concrete paths and packet fields. Reply in the response format included in this message, with `reviewer: codex`; keep uncertainty visible. A proposed execution step is a recommendation only.

Read-only sandboxing constrains project file writes. It does not turn the review into an approval-gated analysis run or prove that a model's critique is correct. Claude must inspect the response and the actual repository state. If plan review is invoked directly in Codex, return this critique only; Claude remains responsible for synthesis.
