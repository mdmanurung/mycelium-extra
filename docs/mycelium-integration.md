# Relation to Mycelium

[Back to README](../README.md)

Mycelium Extra complements Mycelium without overriding it. Concretely:

- `grill` makes no edits. It never writes `.living/`, manifests, todo, or analysis files. It never runs repository scripts by path, because that would start Mycelium's post-action cycle. Its data checks use inline read-only probes.
- `decision-status` writes to `.living/decisions.md` only after you confirm a resolution, and only by appending. Its parser runs from stdin (`python3 - ... < decision_threads.py`), which the Mycelium 0.6.0 and 0.7.2 hooks do not treat as a post-action run.
- `data-contract-check` is read-only and runs the same way. Its contract stays outside the repository until you approve the plan.
- `new-analysis` writes only inside the new folder. Its script also runs from stdin. The folder uses Mycelium's layout (`<NAME>.md`, `outputs/`, `reports/`, `run.sh`) plus a plan, a tracker, a Snakefile, and `data/` and `code/` links, so `/mycelium:analyze` continues it as an existing analysis rather than building a second skeleton.
- After you approve a plan, run it through your normal workflow. In a Mycelium project that is `/mycelium:analyze` (`$mycelium:analyze` in Codex), which logs the brief's "Decisions to record" through Mycelium's lifecycle.
- `verify` reads Mycelium's lineage but never writes `.living/`. Its report is read-only. Its `write` step runs from stdin and writes only `<analysis>/provenance/`. Those new files make Mycelium's Stop hook ask for a `.living/` update, where you record the verify status through Mycelium's normal logging.
- `/mycelium:review grill` reviews an existing analysis or diff; `grill` plans before execution. Use both.
