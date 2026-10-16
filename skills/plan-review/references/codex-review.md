# Codex engineering review

In Claude Code, invoke a fresh Codex task rooted in the verified workspace and the canonical packet on stdin, after `review_packet.py verify` has printed the file list (see `SKILL.md` and the payload boundary in [review-contract.md](review-contract.md)). Use the installed CLI's read-only sandbox and ephemeral session, for example:

```bash
codex exec --sandbox read-only --ephemeral --ignore-user-config -C <packet-folder>/workspace - < <packet-folder>/packet.txt
```

`--ignore-user-config` skips `~/.codex/config.toml`, so no plugins or hooks load (authentication still works). In a repository with `.living/`, Mycelium's Codex hooks otherwise run in the reviewer session and add session-resume and audit instructions that are not part of the packet. If the user's Codex setup needs its config (for example a custom provider), drop the flag and say so in the reviewer status.

Codex reads the repository, not only the packet: rooted in the repository, a read-only sandbox still lets it open any file under the working root, including `data/`, raw files and `.env`, and what it reads is sent to OpenAI. So root it on the data-free copy that `prepare` built: `workspace/` holds only the explicitly selected code and document attachments, hashed in the manifest. Do not root it in the repository, and do not add files to the workspace after `verify`. A read-only sandbox is not known to confine reads to the working root, so a path outside it may still be readable; this workspace limits what Codex is given, not what the host lets it open. If the user declines the data-free copy and wants the repository as root, add to the role prompt: do not open files under `data/`, raw or participant-level tables, `.env`, key files or credentials, and say in the reviewer status that Codex could read the repository beyond the packet. An instruction is not enforcement. Without `verify` having succeeded, say in the status that the send was not byte-bound.

Do not use a write sandbox, `--dangerously-bypass-approvals-and-sandbox`, or a Codex implementation worker. Inspect the CLI help for the installed version before using flags. If the CLI, authentication, a usage limit, the sandbox, or project hooks prevent a read-only run, report Codex unavailable: an `ERROR:` line or a reply without the response format is never a clean review. Check the target repository's tracked and relevant ignored state before and after the review; unexpected changes invalidate the read-only claim.

Give Codex the packet and this role:

> Review implementation feasibility, repository compatibility, dependency order, available APIs, data flow and leakage, reproducibility, testability, failure handling, validation, and plan-to-code divergence. Do not redesign the scientific question, edit files, run project scripts, or approve the plan. Cite concrete paths and packet fields. Reply in the response format included in this message, with `reviewer: codex`; keep uncertainty visible. A proposed execution step is a recommendation only.

Read-only sandboxing constrains project file writes. It does not turn the review into an approval-gated analysis run or prove that a model's critique is correct. Claude must inspect the response and the actual repository state. If plan review is invoked directly in Codex, return this critique only; Claude remains responsible for synthesis.
