# Independent expected values

An expected value is independent when the code under test did not make it. Four sources work. Use the first that fits.

1. **Hand-computed literal on a toy table.** Three donors, six rows, numbers you can add in your head. Write the answer into the check as a number.
2. **Simulated dataset with known truth.** You set the effect, so you know what comes out.
3. **Published value.** A number from the paper or the package vignette, with the table or page named in a comment.
4. **Negative control.** Permute the labels, or use a contrast that has no effect by design. The result must be null.

Not independent: the previous run's output, a value from the same function called on the same input, a snapshot you accepted without checking.

## Toy table

Paired difference, three donors. Treated minus control per donor is 4, 1 and -1. The mean is 4/3. A donor with one condition only is dropped and reported. See `examples/paired_check.py`.

## Simulate with truth: R

```r
set.seed(1)
n_donor <- 6
n_gene <- 200
true_lfc <- c(rep(1, 20), rep(0, n_gene - 20)) # first 20 genes up by 1 (log2)
donor_eff <- rnorm(n_donor, sd = 0.3)          # donor baseline shifts
mu <- outer(rep(5, n_gene), rep(1, 2 * n_donor)) # log2 mean, genes x samples
cond <- rep(c("ctrl", "trt"), each = n_donor)
donor <- rep(paste0("d", 1:n_donor), times = 2)
mu <- mu + outer(rep(1, n_gene), donor_eff[rep(1:n_donor, 2)])
mu[, cond == "trt"] <- mu[, cond == "trt"] + true_lfc
counts <- matrix(rnbinom(length(mu), mu = 2^mu, size = 20), nrow = n_gene)
```

The check: the first 20 genes have a positive estimate, and the median estimate of those 20 is near 1 (a tolerance the user approved). The rest centre on 0.

## Simulate with truth: Python

```python
import numpy as np

rng = np.random.default_rng(1)
n_donor, n_gene = 6, 200
true_lfc = np.r_[np.ones(20), np.zeros(n_gene - 20)]
donor_eff = rng.normal(0, 0.3, n_donor)
mu = 5 + np.tile(donor_eff, 2)[None, :] + np.zeros((n_gene, 2 * n_donor))  # ctrl then trt
mu[:, n_donor:] += true_lfc[:, None]
counts = rng.negative_binomial(20, 20 / (20 + 2**mu))
```

Keep the seed in the check file. A different seed is a different test, so change it only on purpose.

## Negative control

Shuffle the condition labels within donor, rerun the step, and require that no gene passes the plan's threshold beyond the rate the plan states. Shuffle within donor, not across, so the pairing stays intact.

With two conditions, a within-donor shuffle only swaps or keeps each donor's labels. Six donors give 2^6 = 64 label sets. Random draws can repeat the real labelling or its exact mirror, and the mirror gives the same absolute effect. Such a run still holds the real signal, so the control is void. List all the label sets, drop the real one and its mirror, and run a stated number of the rest (the replicate count is an impactful choice). With few donors the list is short, so say how many null sets exist. If that number is too small to bound a false-positive rate, report the control as `unsupported`.

## Worked example: known-contrast pseudobulk

Claim: the pseudobulk step sums counts per donor and condition, and the contrast treated minus control has the right sign and size.

Toy input, one gene, 2 donors, cells listed by row:

| donor | condition | counts in cells |
|---|---|---|
| d1 | ctrl | 1, 2, 3 |
| d1 | trt | 4, 4 |
| d2 | ctrl | 0, 5 |
| d2 | trt | 6, 2, 2 |

Hand sums: d1 ctrl 6, d1 trt 8, d2 ctrl 5, d2 trt 10. Treated minus control per donor: 2 and 5. Mean 3.5.

The check reads the step's pseudobulk table and requires four things:

- the four sums above, matched by donor and condition name
- total counts conserved per donor (d1: 14, d2: 15)
- the per-donor difference is positive for both donors (sign)
- shuffling `condition` within donor makes the sums swap, so the difference flips sign

A step that averages instead of summing fails the first line. A step that matches rows by position fails when the input rows are shuffled. Both are red before the step exists.

What passing shows: the aggregation and the contrast sign work on this table. It does not show the model, the filter thresholds or the biology are right.
