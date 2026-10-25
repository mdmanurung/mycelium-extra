# Plan evidence: commands a reader can re-run

A plan's Evidence bullet says what a file holds. A `<!-- plan-evidence -->` block records the read-only
command that showed it, so `verify` can re-run the command later and compare the output with what the
plan recorded. The point is that nobody retypes a number: the output in the block is the output the
command printed.

It also gives `explain plan` (see [socratic.md](socratic.md)) its material, and `track-changes` the
row graph its walkthrough view draws.

## Format

One block per message, below the plan table, beside the other comment blocks:

```text
<!-- plan-evidence {"version": 1, "rows": [
  {"row": "2", "depends_on": ["1"], "evidence": [
    {"claim": "34 paired samples", "cmd": "rg -c '^S' data/samples.tsv", "out": "34"}]}
]} -->
```

| Field | Meaning |
|---|---|
| `row` | the plan table's id (or position) this evidence supports |
| `depends_on` | the rows whose output or choice this row consumes; `[]` for a first step |
| `claim` | what the output shows, 120 characters or fewer |
| `cmd` | the read-only command, run from the project root |
| `out` | the command's output, pasted verbatim, at most 40 lines |

## Rules

- Paste the output you got. Do not reformat it, summarise it, or copy a number from somewhere else.
- One command per entry, 500 characters or fewer, and no output redirection.
- Read-only programs only. `verify` re-runs a command through a guard and reports anything else as
  `not checked`, so a command it will not run is dead weight in the plan. The guard allows `rg`,
  `grep`, `cat`, `head`, `tail`, `wc`, `nl`, `ls`, `find` (without `-exec` or `-delete`), `diff`,
  `sort`, `uniq`, `cut`, `tr`, `comm`, `paste`, `basename`, `dirname`, `realpath`, `stat`, `file`,
  `sha256sum`, `shasum`, `md5sum`, `jq`, and `git` with a reader subcommand (`log`, `show`, `diff`,
  `status`, `blame`, `rev-parse`, `ls-files`, `ls-tree`, `cat-file`, `describe`, `shortlog`, `grep`,
  `show-ref`). Use `rg -n` or `head -n` for a line excerpt: `sed` and `awk` are not allowed, because
  either can write from inside its own script.
- A flag is checked too, because an allowed program can write or run another program: `sort -o`,
  `sort --compress-program`, `git log --output`, `git grep -O`, `git -c <key>=<value>`, `rg --pre`,
  `find -fls` and `file -C` are all rejected.
- Record a command whose output is stable. A timestamp, a duration, a colour code or an absolute
  path that differs per machine turns every later check into `changed`.
- Exit 1 is fine, since a reader uses it to say "no match" or "differs". Exit 2 or more is `not checked`
  with the status, and a command that times out (10 s) is `not checked` too.
- At most 40 entries. Record the three to six facts the plan's validity rests on, not every file you
  opened.
- A property a data probe established (dimensions, columns, sample counts) has no place here unless a
  reader above can show it. When it cannot, keep the brief's `unverified` wording and make checking it
  the plan's first validation step.
- Every Evidence bullet tagged `[agent-derived: <path>]` whose fact a reader would show should have an
  entry. A plan that reads no file gets no block: do not invent one, and do not write a command you did
  not run.

An output in the block shows what a file held when the plan was written. It does not show that the
claim it supports is scientifically right, and `verify` reports `still true` for an unchanged output,
not for a true statement.
