# Triage rubric

Adapted from Fischbach and Walsh, "Problem choice and decision trees in science and engineering", *Cell* (2024), through the Scientific Problem Selection skill (`anthropics/knowledge-work-plugins`, `bio-research`). Choosing the problem matters more than polishing the execution, so spend a few minutes here before spending weeks there.

## Impact: two axes, by type

| Type | The idea is mainly to... | Axis 1 | Axis 2 |
|---|---|---|---|
| Basic science | understand something | Generality: how many systems it applies to | Learning: how much it changes what we know |
| Tool or method | enable experiments | Breadth: how many labs or analyses would use it | Criticality: how much they need it |
| Application | solve a practical problem | Benefit per person | People reached |

Rate each axis low, medium or high. One high axis is enough. If both are low to medium, rethink the idea. A tool that is neither broad nor critical is probably not worth building. When no type fits, define one custom metric and say why the standard ones fail.

## Likelihood

- **Miracles:** count the things that must all go right. Several miracles mean refine the idea or drop it. Zero risk usually means incremental work.
- **Riskiest assumption:** rate how likely it is to hold, and note months until a test can show it.

| Score | Meaning | Chance it holds |
|---|---|---|
| 1 | Very likely | above 90% |
| 2 | Likely | 70-90% |
| 3 | Uncertain | 40-70% |
| 4 | Unlikely | 10-40% |
| 5 | Very unlikely | below 10% |

List assumptions of two kinds: Type A (how the biology or data is, fixed) and Type B (what the method or tool can do, may improve). Probe them with: what must be true about the biology; what the method must do; what the design assumes; whether the analysis can deliver; whether the result can be validated; whether it will be interpretable. Try to prove each wrong.

## Red flags

- A risk 4-5 assumption that cannot be tested for more than 18 months.
- More than two assumptions at risk 4-5.
- High-risk assumptions that depend on one another.
- The low-risk work is planned first and the high-risk test is put off.
- A risk-5 assumption more than three years out: choose another idea.

## Green lights

- The riskiest assumption can be tested within 6 months.
- More than one path to success, or a fallback when one assumption fails.
- Risk spread across the timeline, not at the end.

## Go/no-go test (top idea only)

Write: the specific question; the most direct test, even if crude; the result that means go; what to do on failure (pivot or stop); the time; the data or resources it needs. If the idea fails the test cheaply, that is the best outcome of triage.

## Making an idea better

Move the test earlier, run several candidates in parallel, reframe the question, change the system or dataset, or add a complementary approach. Offer these under `reframe`.
