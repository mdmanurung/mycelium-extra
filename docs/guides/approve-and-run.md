# Approve and run

The gate denies a covered run until you approve a plan that names it. It then records each run as a receipt.

**Method habits 3 and 4** ([the method](../start/method.md)). Without the plugin: commit the plan with a sign-off line, run only the scripts it lists, and keep experiments in a folder whose outputs you never cite.

## What you control here

- **Your typed word:** `approve plan <hash>`, `approve amendment <hash>`, `approve freeze <hash>`, or bare `approve` when exactly one card is waiting and it is the one shown last. Only these exact words count. `ok, approve` is an ordinary prompt.
- **Shown to you:** the approval card, a denial with its reason, and a notice when a pinned input changes or a script is re-pinned after an edit.
- **To say no:** don't approve. To turn the gate off, remove `.mycelium-extra/gate.json`. Exploration is a separate, typed grant (below).

## Steps

1. Turn the gate on once (`init`, see [your first plan](../start/first-plan.md)). Check that the gated paths cover your analysis folders.
2. Get a plan from [grill](plan-an-analysis.md). Its status line makes the Stop hook show a card with the hash.
3. Check the science on the card. To see more, type any of:

   ```text
   card 84bb5fce full
   card 84bb5fce checks
   card 84bb5fce diff
   ```

4. Approve in the same session that showed the plan:

   ```text
   approve plan 84bb5fce
   ```

   With no card waiting, or two or more, nothing is approved and the reply lists the pending hashes.
5. Run the steps. The gate stays silent for a covered run and records a receipt.

### Debugging without a new approval

```text
allow explore 84bb5fce
stop explore
```

`allow explore <hash>` lets the agent fix and re-run code on that plan's own analysis paths with the `MYCELIUM_EXTRA_EXPLORE=1` prefix. The gate denies any path outside them. Plain `allow explore` is the broader, session-wide grant. Explore runs are logged, are not reportable, and never become results. To report them, ask grill to promote them to a plan.

### Optional

`hints on` and `hints off` switch one-line command suggestions on and off. Other `gate.json` settings (approval hours, run limit, `pin_scripts`) are on [Advanced features](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/advanced.md).

## Worked example

This is real harness output on the fixture project (synthetic names). Before approval, the agent tries step 1:

```text
$ python3 analysis/vaccine-response/scripts/01_select_samples.py

mycelium-extra gate: blocked because no active approved plan covers this run.
  - python3 analysis/vaccine-response/scripts/01_select_samples.py
Active approved plans (last 24 h): none.
Present a plan whose plan table names these paths (prose, Evidence, and Source citations do not count) and that ends with the grill status line; the user approves it by typing `approve plan <hash>`. Do not work around this block; if the user wants an exploratory run instead, they will say so.
```

After you type the approval:

```text
> approve plan 84bb5fce

mycelium-extra: plan 84bb5fce approved. Gated runs whose paths appear in that plan may run for 24 h. Pinned inputs: data/processed/vaccine-cohort/sample_metadata.tsv, data/processed/vaccine-cohort/counts.tsv. Pinned scripts: analysis/vaccine-response/scripts/01_select_samples.py, analysis/vaccine-response/scripts/02_paired_test.py, analysis/vaccine-response/scripts/03_summary.R.
```

The three steps then run with no hook speaking. The full card is in [a worked example](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/example.md#4-the-approval-card).

## What this does not guarantee

The gate reads the words of a shell command. It does not trace `make`, `bash script.sh` outside the gated paths, `xargs python3`, or code run through MCP notebook tools. It infers exit status from which hook fired. It catches mistakes; it is not security. See [what this does not guarantee](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/not-guaranteed.md).

## Reference

[gate](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/gate.md) · [gate.json](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/gate-json.md) · [state files](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/reference/state-files.md) · [control model](https://github.com/mdmanurung/mycelium-extra/blob/main/docs/concepts/control-model.md) · next: [verify and provenance](verify-and-provenance.md)
