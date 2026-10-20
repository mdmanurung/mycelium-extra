# E07. verify: a planned command never recorded, an unplanned script ran

Control point: **honesty**

Anonymised from a real project. Source: a real saved `verify` report in project A (status CONFORMS_WITH_GAPS): the plan named the workflow tool but no run of it was recorded, two scripts ran after approval that the plan table did not name, and the plan had no `Outputs:` line. The report below is regenerated on the fixture with the same shapes.

## 1. Socratic: ask these first

- Which steps does "conforms" cover, and which words in the status say gaps remain?
- A script ran that my plan never named. Who asked for it, and under which approval?
- Without an `Outputs:` line, what can the record tie a result file to?

## 2. What the tool showed (excerpt, regenerated)

```text
# Verify plan <hash>: CONFORMS_WITH_GAPS
Ran as planned  no: 1 of 4 steps ran to completion; not completed: <script> (no receipt); ...
Code checks     lint clean
Next            close the first gap: `<script>`: no run under this plan was recorded.

- gap: The plan names `snakemake`, but no `snakemake` run under it was recorded.
- gap: `analysis/example/scripts/04_extra_plot.py` ran since the approval but is not in the plan table.
- info: Run under another plan: `python3 analysis/example/scripts/04_extra_plot.py` ... (under plan <other hash>).
Verify status: CONFORMS_WITH_GAPS
```

(In the original the two unplanned scripts and the missing `Outputs:` line were three gaps.)

## 3. Track-changes shape

Observed: runs recorded under this approval. Potential: results from the unplanned scripts may be quoted as if planned. Gap: no run of the named workflow tool; outputs not tied to a run. Unknown: computation outside the gate's hooks (notebook tools).

## 4. Librarian block

None.

## 5. What the human decided

Keep the status as written (no upgrade to "conforms"), write provenance with the gaps, and add the missing `Outputs:` line in the next plan.

## 6. Without the tool

The folder would read as "ran as planned". The unplanned scripts' results could have been cited with no flag.

Basis: project A: 3 provenance bundles; this episode is one of them.
