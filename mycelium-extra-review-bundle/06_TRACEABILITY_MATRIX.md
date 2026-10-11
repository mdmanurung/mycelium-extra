# Mycelium Extra — Review Finding to Backlog Traceability (scope-aligned)

Links review findings and known misses to tasks in `03`. The last column names what Mycelium already provides and
Extra consumes (`G13`); "—" means Extra owns it.

| Review finding / defect | Remediation | Mycelium source consumed |
|---|---|---|
| `CONFORMS` can be overinterpreted | `M0-T01` (statuses at `docs/verification.md:29`) | — |
| Threat model scattered | `M0-T02` (`docs/approval-gate.md:103,109`) | — |
| Claude/Codex guarantees differ | `M0-T03` | — |
| Division of labour not stated as non-goals | `M0-T09` (`docs/mycelium-integration.md`) | all |
| `HANDOFF.md` goes stale (header d4391b0 / 0.9.42; repo 72119ef / 0.9.43) | `M0-T04` (with B5); check in `M7-T10` | — |
| Branch protection | `M0-T06` (maintainer; needs a push; not a gate) | — |
| Schemas need consistent versioning | `M0-T07` (includes migration note) | — |
| Mycelium version drift (A5) | `M0-T08` | — |
| No first-class execution identity | `M1-T18` spike, `M1-T01`–`T04` | data-lineage events (join key) |
| `V-20` wrong output attribution | `M1-T05`, `T06`, `T08`, `T09` (`T07` parked); HPC via `M6-T08`–`T10` | `.living/log/data-lineage/<session>.json` |
| `V-02b` partial output looks successful | `M1-T10`–`T13` | `analyze` validation requirements (checked first) |
| Reportable runs need stronger guarantees | `M1-T14`–`T17` (includes C2) | — |
| grill may miss consequential choices (LLM step untested) | `M2-T01`–`T07`, `M2-T18`, `M2-T12`; re-run `M4-T13` | — |
| Sibling-repo failures not fed back | `M8-T03` → `M2-T19`; `M8-T05`, `T06` | — |
| Scientific intent mostly prose | `M3-T01`–`T05` (Choice block in the plan) | — |
| Sample misalignment (`DC-09`) | `M3-T06`, `T07` | — |
| Reversed contrast (`DC-08`) | `M3-T08`, `T10`, `T17`; `M7-T08` (direction claim kind) | `mycelium:review` tripwires (known-answer, metamorphic) |
| Gene-symbol corruption (`DC-10`) | `M3-T11`, `T12` | — |
| Normalization / data-state mismatch (`DC-11`) | `M3-T13`–`T15` (AnnData `X`/layers inside `data-contract-check`) | — |
| Output expectations duplicated | `M3-T16` | — |
| Numbers in prose vs outputs | existing D1 claims block; `M7-T08` | `register_value` → `outputs/numbers.json` → scitexlintr |
| Pinned inputs vs original ingest | `M6-T05` | `data/DATA_MANIFEST.md`, `provenance.md` (SHA256) |
| R / Bioconductor reproducibility | `M6-T03` | — |
| Submission-time HPC receipt ≠ compute node | `M6-T08`–`T10` | not tracked by Mycelium (`sbatch`) |
| Provenance format | `M6-T11` (schema field on `PROVENANCE.md`) | — |
| External plan review privacy | `M7-T01`–`T05` | — |
| AI-use disclosure written from memory (D3) | `M7-T16` | — |
| No worked example (A6) | `M7-T15` | — |
| Setup and host problems hard to diagnose | `M7-T10` | — |
| Hook and user messages heavy | `M7-T14` (wording only) | — |
| No lab-colleague validation | `M8-T09`, `M8-T01`–`T04` | — |
| Snakemake envs; containers; GPU; remote inputs | `M6-T01`, `T02`, `T04`, `T06`, `T07` (parked) | — |
| Citation checking (D2) | `M7-T06`, `T07` (parked) | — |
| Anti-gaming (D10–D12) | parked (`05`) | — |
| Error-reduction vs no Extra | Track R in `03` (optional) | — |
| Release maturity | `M9` (parked: publish decision) | — |

# Known-miss closure targets

| Defect | Required end state |
|---|---|
| `V-20` | Correct lineage (Mycelium's, else Extra's) or unresolved gap for foreground runs; background and `sbatch` outputs `unresolved` until `M6-T08`–`T10`; never wrong confident attribution. Lineage file absent = gap. |
| `V-02b` | An incomplete declared output fails output-integrity validation. |
| `DC-09` | A sample-key check prevents positional or misaligned analysis. |
| `DC-08` | Direction mismatch detected where an output or claim declares a direction; otherwise listed as unresolved. verify reports whether the direction tripwire ran. Full detection in arbitrary code is not attempted. |
| `DC-10` | Corrupted identifiers are caught. |
| `DC-11` | Declared vs actual data state is detectable at a basic level; absent reader = gap. |

Known-miss tests stay in the repository after fixes, with the expected behavior inverted.

# Evaluation traceability

```text
M2 plan-stage scenarios + grill-coverage baseline (current release)
        ↓
M3 plan Choice block, informed by failures; scenarios kept apart from the design set
        ↓
M4 frozen release re-run, before vs after
        ↓
M8 sibling repos and lab colleagues feed new defect cases and scenarios
```

The scenarios used to design M3 are not used to judge it.
