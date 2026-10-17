# Using Mycelium together with Extra

**Mycelium manages the project. Extra plans and verifies its runs.**

You can use Extra in an ordinary repository. Add
[Mycelium](https://github.com/arjunrajlaboratory/mycelium) when you want its
project memory, analysis conventions, code review, and reports.

**Tested with Mycelium 0.6.0 and 0.7.2.** Extra's hook and file checks (for example, that a
script piped through stdin is not counted as a post-action run, and that `Status` in
`decisions.md` is read as body text) were checked against those versions. `/mycelium-extra:init`
reads the version that `.mycelium/plugin-root` points at and prints one line when it is another
version, or cannot be read. It never writes Mycelium's files, and says nothing in a repository
without Mycelium.

## Who does what

| Task | Use |
|---|---|
| Read existing decisions and plan the next analysis | Extra's `grill` |
| Create an analysis folder with a plan and tracker | Extra's `new-analysis` |
| Approve covered execution and record receipts | Extra's approval gate |
| Implement and execute the analysis | Your normal runner or Mycelium's `analyze` |
| Check the approved plan against the execution record | Extra's `verify` |
| Review code and statistics before the final freeze; produce a report | Mycelium's `review` and `report` |
| Maintain decisions, learnings, and findings | Mycelium's normal lifecycle |

## Use an existing Mycelium project

Follow [Usage tiers](usage.md); Extra reads the project's `.living/` records,
analysis docs, and conventions before planning. Use `new-analysis` only when
you need a new folder. After approval, `mycelium:analyze` continues that folder.
For reportable work, freeze the finished code in a run plan, run it, and verify.

Ask Mycelium's `review` to check the methods and code against the approved plan
before the final freeze (see [Usage tiers](usage.md#two-checkpoints)). After
saving provenance, ask for another review only if `verify` leaves findings
unresolved or a result needs a closer look; it can use
`<analysis>/provenance/plan-<hash>.md` as the plan. Record the verification
status through Mycelium's normal memory updates.

## What Extra reads from Mycelium

This is everything the shipped code reads, plus what its skills tell the agent to
read. Upstream paths are in [Mycelium](https://github.com/arjunrajlaboratory/mycelium)
(checked at commit `8f8b167`, plugin version 0.9.1; the versions in this guide are
three different checks: 0.6.0 and 0.7.2 are the releases Extra's hooks were tested
against, 0.9.1 is the upstream the lineage format and this table were read from, and
the fixture project follows 0.8.1). Extra never imports Mycelium's code, and the one
place it runs any is `idea`, which calls Mycelium's `upsert_table_row.py` as a
subprocess; the one test that imports it,
`tests/test_contract_compatibility.py`, loads upstream's `data_contract_check.py`
read-only from the checkout named by `MYCELIUM_UPSTREAM` and skips that half when
there is none.

| Record | Upstream path | Read by | Used for | When absent |
|---|---|---|---|---|
| Data-lineage manifest | `.living/log/data-lineage/<session>.json`, written at Stop by `skills/core/scripts/extract_data_lineage.py` (format: `skills/core/references/data-lineage.md`) | `verify` (`lineage_actions`): each action's `ts`, `script`, `bash_cmd`, `bash_exit`, `io_detection`, `outputs` (path, `sha256`, `_missing`), `lineage_warnings` and the manifest's `extraction_warnings` and session id | A script that lineage saw run in the plan's window, that the gate did not record and the plan does not name, is a gap; script-less (inline) commands are counted and not checked. An action that lists an output is also a `lineage-record` candidate producer for it, only when joined to one matched attempt, never `supported` (see below) | No lineage gaps and no message; unreadable files are skipped |
| Analysis manifest | `analysis/ANALYSIS_MANIFEST.md` (any `*ANALYSIS_MANIFEST.md` that git lists, else that path) | `verify status`: the entry's status word | A `manifest` column | Shown as `not listed` |
| Registered values | `analysis/<name>/outputs/numbers.json`, written by `skills/core/scripts/register_value.py` | `verify`, only when a `<!-- claims -->` line names the file | The claimed number is compared with that cell, read as ordinary JSON: dotted keys, and list entries by position (the fragment's `values` list is not looked up by `key`) | The claim is a gap ("unverified"), not a pass |
| Pointer to the Mycelium install | `.mycelium/plugin-root` | `init` (version notice, `--diagnose`), `new-analysis`, `idea` (to find the helper) | A one-line note when the version is not 0.6.0 or 0.7.2; Mycelium's `skills/core/templates/analysis-readme.md` for the analysis doc | No note; `new-analysis` uses its bundled copy of the 0.7.2 template |
| `.living/` folder | `.living/` | `gate`, `new-analysis` | Whether the repository is a Mycelium project: the unignored-state warning, post-run reminders to follow Mycelium's post-action protocol, the `UPPER_SNAKE_CASE.md` analysis-doc name | Treated as an ordinary repository |
| Todo registry | `todo/TODO_REGISTRY.md` and `todo/<slug>.md`, rows written with Mycelium's `skills/core/scripts/upsert_table_row.py` (found through `.mycelium/plugin-root`, else `~/.claude/plugins/installed_plugins.json`) | `idea` (writes), `idea-triage` (reads, annotates, sets a picked item's Status) | A parked idea in Mycelium's own todo format; the next idea to work on | `idea` creates `todo/` and the registry; `idea-triage` says there is nothing to triage |
| Decisions and learnings | `.living/decisions.md`, `.living/learnings.md` | `decision-status` script (`learnings.md` only with `--include-learnings`); `harden` (instructions) | Which decision still binds; the learning to harden | The skill says so and stops |
| Project memory for planning | `MYCELIUM.md` or the Mycelium block in `CLAUDE.md`/`AGENTS.md`, `.living/INDEX.md`, the manifests, `.living/findings/`, conventions, `.living/outputs/reviews/`, `.living/log/LOG_REGISTRY.md`, `~/.mycelium/knowledge/` | `grill` and `plan-review` (instructions in [`references/mycelium.md`](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/grill/references/mycelium.md)); no code parses these | The plan's sources | Missing manifests, index or findings are treated as normal partial states |

`verify stale` prints an `rg` command for `.living/findings/`; it does not read the
findings. No Extra code reads Mycelium's tripwire documents, review outputs or
conventions (`grill`'s instructions do point the agent at the last two).

## Evidence limits

- **Lineage is static, and it is not proof of who produced a file.** Upstream
  detects a run from the command line and finds its inputs and outputs by static
  scanning (`io_detection: "static"` or `"unresolved"`), then writes the manifest when
  a session stops. It covers finished sessions only, and which commands it detects
  depends on the Mycelium version: Extra's post-run reminder assumes the 0.7.2
  detector (python, R, jupyter), while the 0.9.1 lineage reference also lists pipeline
  runners. A lineage record is candidate producer evidence only: it is used for an
  output when an explicit id or a unique session, command, script and time match joins it to one
  matched attempt, the join is stated as inferred, and it is ignored for
  `unresolved` detection, a nonzero exit, a missing path, a hash that differs from the file,
  or an attempt that watched the output and did not see it change. Upstream fills missing hashes
  from disk later, so a hash is not proof. It can confirm an observed producer or add a second
  one (unresolved); it never sets a `supported` producer.
- **A tripwire audit describes tests; it does not run them.** In Mycelium's
  `skills/core/references/review/deep-tripwires.md`, *audit* writes a plan of what
  would be tested, *scaffold* proposes the instrumentation, and only *run* executes
  checks and reports pass or fail. An audit document cannot show that a test passed,
  and Extra does not accept one as an executed check.
- **A registered number is mutable across runs.** `register_value` upserts: a later
  run replaces the earlier value silently, so a matching `numbers.json` cell shows the
  file's current content, not which run wrote it. Use the claims check to catch a
  number that disagrees with its cell, and `verify` for what ran.

## Optional routing through `analyze`

Upstream's `analyze` skill does not call Extra, and Extra offers no API for it to do
so. Hints in Extra's skills and hooks are advice to the agent. Routing planning,
approval, or verification through `analyze` would need an agreed upstream
contribution; it is future collaboration, not a current integration.

## Boundaries

Extra's planning and data checks are read-only. Scaffolding writes only the new
analysis folder; verification writes only its `provenance/` after confirmation.
`decision-status` appends a confirmed resolution; `harden` updates one confirmed
learning after demonstrating its test. `idea` writes under `todo/` only (one item
file and one registry row, with no questions asked), and `idea-triage` annotates
those items and sets a picked item's Status. Extra does not replace Mycelium's memory
or code review. Independent plan review advises; only your approval authorizes runs.

The gate keeps its state in `.mycelium-extra/`, apart from Mycelium's `.mycelium/`
and `.living/`, and `init` ignores it in `.gitignore`. Mycelium's stop check counts
`git status`, so if that folder is not ignored in a repository with `.living/`, the
approval card opens with a warning: add `.mycelium-extra/` to `.gitignore`.

## Credits

Extra reuses Mycelium's MIT-licensed analysis template and follows its folder,
decision, finding, and memory conventions (Copyright (c) 2024 Mycelium Contributors).
The bundled template retains the
[Mycelium MIT notice](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/new-analysis/templates/MYCELIUM_LICENSE).
[scilintr](https://github.com/arjunrajlaboratory/scilintr) supplies scientific
linting; data-contract alerts use ClawBio's expected/observed/evidence format.
