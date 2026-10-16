# Synthetic scheduler qualification

Objective: Observe one successful task, one exit-7 failure, two distinct array tasks and one cancellation, then reconcile plugin receipts, scheduler accounting and files.
Inputs: success.sh failure.sh array.sh cancel.sh
Outputs: slurm-*.out slurm-*.err

| Step | Choice | Source | Validation |
|---|---|---|---|
| S1 `sbatch --parsable success.sh` | short partition, 1 node, 1 CPU, no GPU, 1 GiB, 5 minutes | user: approved A09 script | exactly one COMPLETED job and exit 0 |
| S2 `sbatch --parsable failure.sh` | same resource bounds; planted exit 7 | user: approved A09 script | exactly one FAILED job and exit 7; verification remains blocking |
| S3 `sbatch --parsable array.sh` | same per-task bounds, two elements 0 and 1 | user: approved A09 script | two separate element IDs and outputs; no conflated receipt |
| S4 `sbatch --parsable cancel.sh` | same resource bounds; cancel only this returned job ID after its started marker | user: approved A09 script | exact ID CANCELLED and retained partial stdout/accounting |
| S5 inspect `sacct` and retained output files | never infer a missing job is absent or resubmit an unresolved intent | user: approved A09 recovery boundary | four submission intents, five task outcomes, no duplicate live job |

This is a draft for a disposable gated fixture. Present it through the native host and obtain same-session approval after the external packet is approved. No job submission is authorized by this file. Native tool events must generate plugin receipts; scheduler command stdout alone is not plugin dispatch evidence. Do not edit scripts/resources after approval.
