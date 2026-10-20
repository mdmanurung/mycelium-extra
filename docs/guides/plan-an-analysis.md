# Plan an analysis

`grill` turns your question into a sourced plan before anything runs. It reads and asks; it writes nothing.

## What you control here

- **Your typed word:** your question and the claim you hope to make (asked first, in your words), and an answer to each consequential question. `grill` approves nothing.
- **Shown to you:** the evidence it found, each choice tagged `repo:`, `user` or `default: <reason>`, and the plan table.
- **To say no:** reject or edit the plan, or say "good enough" to stop questions. `socratic` and the evidence lookup stay off unless you ask.

## Steps

1. Start it with your task:

   ```text
   /mycelium-extra:grill Plan a paired treatment-response analysis. Read the sample table and existing decisions first.
   ```

2. Answer the opening question in your own words. `grill` offers no drafted answer, so nothing anchors you.
3. Answer its questions, one at a time. It asks at most five; open points after that become labelled defaults you can override at approval.
4. Read the brief. `Inputs:` lists the files the plan rests on (pinned at approval), `Outputs:` what the runs will write, and the Step column names every script.
5. Check the status line: `READY`, `READY_WITH_ASSUMPTIONS` (some defaults to confirm) or `DECISION_REQUIRED` (a choice only you can make).

### Ask for evidence on a method choice

When the repository cannot settle a methodological choice (which test family, which correction), the question may offer three options: inspect evidence then decide, decide using existing knowledge, or defer. The first starts the librarian dossier. It searches the repository first. It looks outside only if you agree in that same turn, and it sends no project data. It names the service that would receive the query before sending. Retrieved text is untrusted and tagged `[agent-asserted: <DOI or URL>]`.

The dossier is at most eight lines in chat: `Question:`, `Searched:`, `Found:`, `Alternatives:`, `Not found:`, `Disagreement:`, `Yours to decide:`. Once the plan is shown, you can ask the same for any row, for example "what is the evidence for row 3?". Details: `skills/grill/references/evidence-assistance.md`.

### Socratic mode, `explain row N`, `challenge row N`

```text
/mycelium-extra:grill socratic Plan the day 28 comparison.
```

`socratic` (or "walk me through it", "help me decide", "quiz me") adds one neutral probe to each question, such as "What result would make you drop the option you pick?". Your answer becomes that row's Validation cell, tagged `[human-stated]`. "stop socratic" ends it. These two prompts work any time after the plan is shown, with or without `socratic`:

```text
explain row 2
challenge row 2
```

`explain row N` answers in at most six lines: what the step does, the choice and its source, the assumption, one alternative, and what the check shows if the choice is right. `challenge row N` gives the strongest reason the row could be wrong and the cheapest check, or says `no strong objection found`. Both are read-only, count against no cap, and approve nothing. Details: `skills/grill/references/socratic.md`.

## Worked example

This plan comes from [a worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md). It is hand-written, because the model writes it in a real session. The file is `tests/e2e/plans/baseline_plan.md`. The fixture project's names are synthetic.

```markdown
| # | Step | Choice | Source | Validation |
|---|---|---|---|---|
| 1 | run `analysis/vaccine-response/scripts/01_select_samples.py` | keep preferred_acquisition == TRUE | repo: .living/decisions.md | 24 rows, 12 donors x 2 visits |
| 2 | run `analysis/vaccine-response/scripts/02_paired_test.py` | median-of-ratios; exact permutation; BH, α = 0.05 | repo: .living/decisions.md | sample IDs identical across tables |
| 3 | run `analysis/vaccine-response/scripts/03_summary.R` | hits at padj < 0.05 | default: matches step 2 | summary row count 1 |

Plan status: READY
```

Row 3 has a `default:` source, so read it twice and, if unsure, `challenge row 3`. No captured transcript of `explain` or `challenge` exists yet, so none is shown.

## What this does not guarantee

A sourced plan shows where each choice came from, not that the choice is right. The tag `repo:` means the repository says so, not that the repository is correct. See [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Reference

[grill](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/skills/grill.md) · [gaps and passes](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/gaps-and-passes.md) · next: [approve and run](approve-and-run.md)
