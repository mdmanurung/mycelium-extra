# Process Run RO-Crate export

`verify crate <hash> --analysis-dir DIR` writes `DIR/provenance/crate-<hash>/ro-crate-metadata.json`. It reads the saved bundle (`verify write` first) and the plan's frozen approval instance. It re-runs, re-hashes and re-grades nothing.

## Pinned specifications

Read on 2026-11-13. No version came from memory.

| What | Pinned value | Source read |
|---|---|---|
| RO-Crate specification | 1.3 (published 2026-06-22), permalink `https://w3id.org/ro/crate/1.3`, context `https://w3id.org/ro/crate/1.3/context` | https://www.researchobject.org/ro-crate/specification/1.3/index.html and `.../root-data-entity.html` |
| Process Run Crate profile | 0.6, `https://w3id.org/ro/wfrun/process/0.6` | https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate |
| Workflow Run Crate profile | 0.6, `https://w3id.org/ro/wfrun/workflow/0.6` (not used, see below) | https://www.researchobject.org/workflow-run-crate/profiles/workflow_run_crate |
| Run vocabulary context | `https://w3id.org/ro/terms/workflow-run/context` | the Process Run Crate page's example |
| Release dates | Workflow Run Crate 0.6 released 2026-09-07 | https://www.researchobject.org/workflow-run-crate/profiles/changelog |

The page text came through a summarizing fetch, so confirm the version strings against the pages above before you cite them in a paper.

## Which profile

The crate declares Process Run Crate 0.6 only. A plan's scripts are tools that ran, not a workflow-engine run with a workflow entity, so the Workflow Run Crate profile (which also requires the Workflow RO-Crate profile) does not apply. The profile is a choice recorded here; changing it changes what a validator checks.

## What the crate holds

- Descriptor `ro-crate-metadata.json` (about `./`, conformsTo RO-Crate 1.3) and root dataset `./` (conformsTo Process Run Crate 0.6, `datePublished` = the date `verify write` saved the bundle, `identifier` = the plan hash).
- One `CreateAction` per matched run of the plan per pinned script it names. `instrument` is the script file entity with its pinned `sha256`; `object` is the plan's pinned inputs; `result` is the outputs whose producer the bundle gives as `supported` for that attempt. It records start and end time and the exit status. It never records the command line, because commands can carry secrets.
- File entities for inputs, scripts, outputs, and the bundle's own plan, receipts, outputs table and evidence file, with the recorded SHA-256.
- An output with no `supported` producer is kept as a file entity, listed in `hasPart`, and carries `mx:producerAttribution` (`candidate` or `unresolved`), `mx:producerGap` and the evidence method. The root lists the count in `mx:gaps`. It is never attached to an action.

## Choices to know

- File ids are paths from the crate folder (for example `../../outputs/fit.tsv`). The crate describes files beside it and copies none. Moving the folder breaks the links, not the hashes.
- Hashes are the recorded ones, not re-read. A file edited after `verify write` still shows its recorded hash.
- `mx:` terms are local (`urn:mycelium-extra:terms:`). A validator treats them as extra properties.
- No `license` is set. Add one before you publish the crate; the licence is yours to choose.
- `object` lists every pinned input for every action, because the bundle does not record which script read which input.
- Output is sorted and has stable ids, so the same bundle gives the same bytes.

## Validation

`skills/verify/tests/test_crate.py` checks the structure (context, root entity, every `@id` referenced exists, recorded hashes match the files, the gap is kept, output is deterministic). It runs the official `rocrate-validator` (profile `process-run-crate`) only when that package or command is installed, and skips otherwise.
