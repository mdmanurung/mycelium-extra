# Background pickup

Read this when the user types `handoff bg`.

1. Check the `## Pending plan (verbatim)` section of `HANDOFF.md`. If it holds donor or patient IDs, sample names or other personal identifiers, do not print the command. Tell the user the prompt would copy them into the job list of `claude agents`, and ask whether to go on. Done when the user answered or the section holds none.
2. Check that the handoff names the pending plan hash under Pending plan. The new agent has no approved plan, so add the hash if it is missing. Done when the hash is in the file.
3. Print this, with `<descriptive name>` filled in (flags `--bg` and `--name` checked against `claude --help`):

```bash
claude --bg --name "<descriptive name>" -- "Approvals are per session and this session has none. Ask me for 'approve' before any gated run. $(cat HANDOFF.md)"
```

Manage the agent with `claude agents`. The skill prints the command and never runs it.
