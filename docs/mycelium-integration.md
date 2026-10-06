# Using Mycelium together with Extra

**Mycelium manages the project. Extra plans and verifies its runs.**

You can use Extra in an ordinary repository. Add
[Mycelium](https://github.com/arjunrajlaboratory/mycelium) when you want its
project memory, analysis conventions, code review, and reports.

## Who does what

| Task | Use |
|---|---|
| Read existing decisions and plan the next analysis | Extra's `grill` |
| Create an analysis folder with a plan and tracker | Extra's `new-analysis` |
| Approve covered execution and record receipts | Extra's approval gate |
| Implement and execute the analysis | Your normal runner or Mycelium's `analyze` |
| Check the approved plan against the execution record | Extra's `verify` |
| Review code and statistics; produce a report | Mycelium's `review` and `report` |
| Maintain decisions, learnings, and findings | Mycelium's normal lifecycle |

## Use an existing Mycelium project

Follow [Usage tiers](usage.md); Extra reads the project's `.living/` records,
analysis docs, and conventions before planning. Use `new-analysis` only when
you need a new folder. After approval, `mycelium:analyze` continues that folder.
For reportable work, freeze the finished code in a run plan, run it, and verify.

After saving provenance, ask Mycelium's `review` to check the code against
`<analysis>/provenance/plan-<hash>.md`. Record the verification status through
Mycelium's normal memory updates.

## Boundaries

Extra's planning and data checks are read-only. Scaffolding writes only the new
analysis folder; verification writes only its `provenance/` after confirmation.
`decision-status` appends a confirmed resolution; `harden` updates one confirmed
learning after demonstrating its test. Extra does not replace Mycelium's memory
or code review. Independent plan review advises; only your approval authorizes runs.

## Credits

Extra reuses Mycelium's MIT-licensed analysis template and follows its folder,
decision, finding, and memory conventions (Copyright (c) 2024 Mycelium Contributors).
The bundled template retains the
[Mycelium MIT notice](https://github.com/mdmanurung/mycelium-extra/blob/main/skills/new-analysis/templates/MYCELIUM_LICENSE).
[scilintr](https://github.com/arjunrajlaboratory/scilintr) supplies scientific
linting; data-contract alerts use ClawBio's expected/observed/evidence format.
