# Benchmark card: gate command classifier

Approved 2026-11-24 (roadmap 19, choices C1-C5). This card is the one authority for the `iterate --mode method` tree and any tusoskill run; tusoskill's own card points here and adds nothing.

## Metric

The pair (false passes, false denies), compared false passes first, then false denies. Lower is better for both. No weighting and no composite score (C1).

- A false pass is a run case whose expected covered target the classifier does not return.
- A false deny is a returned target that the case does not expect.
- Scorer: `python3 tests/bench/score_gate.py <corpus> [--sealed]`, which runs `gate.analyse_command` in a fixed scratch layout with default settings.

## Splits

| Split | File | Cases | Use |
|---|---|---|---|
| dev, seeds | `tests/bench/gate_corpus/seeds.jsonl` | 43, hand-labelled (s38-s43 added after round 1 from reading the code, not from held-out) | the score each candidate is ranked on |
| dev, mined | `tests/bench/gate_corpus/mined.jsonl` | 567, labelled with the output at `789d7d6` | regression anchor: must stay at 0 and 0 unless a label change is reviewed |
| held-out | `/exports/para-lipg-hpc/mdmanurung/mycelium-extra-heldout/gate_heldout.jsonl` | 60 (30 run, 30 benign, 10 families), sha256 `6339a398bcb8603482e256a2c6e73d515fa712a5f1e28e0f24d2a10abecfea02` | scored `--sealed` at baseline and at the end of a round only |

The held-out file lies outside the repository and is read-only. It was written by a fresh agent that saw only the family list, the layout and the coverage rule, not the hooks or the dev seeds. Any read of its content by the implementer or the loop turns it into dev, and a new held-out set is written. Its labels are not adjudicated: a held-out failure may be a label error, and only the user may open the file to check.

## Protected files

The scorer, the corpora, this card and the mining script: `tests/bench/score_gate.py`, `tests/bench/mine_gate_cases.py`, `tests/bench/gate_corpus/`, `tests/bench/card.md`, and the held-out file above.

## What a candidate may change

`hooks/shellwords.py` and the command-parsing section of `hooks/gate.py` (`scoped_segments` to `analyse_command`, about lines 409-1007 at `789d7d6`). Edits go in a worktree, never the live checkout.

## Guardrails for every candidate

- the full suite passes (`python3.12 tests/run_suite.py`);
- gate-diff shows no difference that is not recorded on purpose;
- the planted defects stay at 83 of 83 (`tests/test_end_to_end.py`);
- mined anchors stay at 0 and 0.

Classifier latency is not a guardrail (C5): it measured median 0.09 ms and p95 0.16 ms over 300 calls at `789d7d6`. Fuzz seed for new fuzz cases: 1234.

## Baseline at `789d7d6`

| Split | n | run cases | false pass | false deny |
|---|---|---|---|---|
| dev seeds (s01-s37) | 37 | 29 | 22 | 0 |
| dev seeds (all 43) | 43 | 32 | 25 | 0 |
| dev mined | 567 | 248 | 0 | 0 |
| held-out | 60 | 30 | 12 | 2 |

Figure: `tests/bench/results/789d7d6/gate_by_family.png` (37 seeds), with source data `gate_by_family.tsv` beside it, drawn by `tests/bench/plot_gate_baseline.R`.

Every sealed look is logged in `tests/bench/results/heldout_looks.log`. Round 1 looked three times before the log existed, without tuning on the result. No `freeze-evaluator` ran before round 1; the freeze runs before round 2.
