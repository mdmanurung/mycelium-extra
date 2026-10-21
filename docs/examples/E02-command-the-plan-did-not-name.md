# E02. The plan named the scripts, not the workflow tool

Control point: **consent**

Anonymised from a real project. Source: the amended plan in the same first session as E01 ("the gate rejected a `snakemake` check: the approval covered scaffolding but did not name `snakemake`"). The notices below are regenerated on the synthetic fixture.

![The earlier plan named scripts but not the workflow command. The amended plan included the command and a broader grant that needed inspection, not merely an assumed dry-run permission.](../figures/workflow-grant.svg)

This schematic summarizes the anonymised episode and regenerated card below. A broad command grant can cover more than one dry run, so read its scope before approving.

## 1. Socratic: ask these first

- What did the approved table let run, word for word? Is the workflow tool in it?
- Is this a harmless dry run, or a new thing I have not agreed to?
- What changes in the grant if I approve the amendment: only the one command, or everything?

## 2. What the tool showed

The agent ran a dry-run check with the workflow tool. The plan table had named only the scripts:

```text
mycelium-extra gate: blocked because no active approved plan covers this run.
  - snakemake analysis/example/Snakefile
Active approved plans (last 24 h): <hash>.
```

The agent presented an amended plan with the tool as a new step. The card shows exactly what the amendment adds:

```text
Since <hash> (approved <date>)
  scripts  NEW: analysis/example/Snakefile · SAME: analysis/example/scripts/01_select_samples.py, analysis/example/scripts/02_paired_test.py
  inputs   2 SAME
  plan     objective SAME · steps: 2 same, 1 new or changed
  scope    NEW: analysis/example/Snakefile, snakemake

CAN RUN (in full) · broad grant: any arguments
  command  snakemake  (any invocation)
```

Note the grant is "any invocation" of the command: the card says so; the researcher decides whether that breadth is acceptable.

## 3. Track-changes shape

Observed: plan step count 2 -> 3; one new script in scope; one new command in scope. Potential: a broader command grant than a dry run needs. Gap: nothing yet ran under the new step. Unknown: what the workflow file does when run for real.

## 4. Librarian block

None (not a methodological question).

## 5. What the human decided

Approved the amended hash. Other denied commands in the project needed the same route; the researcher kept the habit of reading the scope lines before typing approve.

## 6. Without the tool

The dry run would have gone ahead unseen, and the first real launch of the workflow would not have needed a conversation about its breadth.

Basis: 144 approvals across two projects; this pair is one of the "amended execution plan" follow-ups.
