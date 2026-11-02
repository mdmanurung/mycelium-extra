# Stress test, 2026-11-02

**Verdict: 40 defects found in 0.22.1; 39 fixed in 0.22.2.** Finding 19 was left: `plan-review` already explains why `review_packet.py` runs by path.

Audited source: `85fe138`, plugin 0.22.1. Five read-only agents probed disposable clones: the 0.22 gate features, the scaffold and report scripts, `verify` and `track-changes`, the smaller skill scripts, and skill text against code. Fixes landed in `d72ec41`..`39660c4`; each code fix has a regression test.

Limits kept after the fixes: a state-folder path split across strings (`'.myc'+'elium-extra'`) still passes the gate, read-only `python -c` naming the state folder stays allowed, and `review_packet prepare` refuses without `gate.json` only when `--root` is absent.

Not proven: the seven `verify` and `track-changes` regression tests were not run against the old code.

The findings below are as reported, before the fixes. C = confirmed by a repro; P = plausible.

Baseline before the fixes: every test file, ablations (17/17), adversarial audit (139 passed), links (580), gate_diff (59 expected differences, exit 0) and the OpenCode node tests (22/22) passed on python3.11. So none of the 40 was covered by an existing test.

Python 3.6 is safe. `py.sh` refuses it for scripts; in hook mode `gate_run.py` denies with a 3.9 message.

## Tier 1: breaks real sessions

1. gate.py:3875-3899 goal_ended (C) — an old goal_status met/failed in the transcript ends a NEW /goal pause at the next prompt. Fix: store transcript size at /goal time; count only statuses past it.
2. gate.py:1077 writes_state (C) — `off.json` / `goal/<session>.json` can be created by `env -C`, `make -C`, perl, awk, python -c, split paths; one empty file turns the gate off. Fix: treat env -C / make -C as cd; ignore off/goal files without a numeric off_at/set_at written by the prompt hook.
3. repo-setup/SKILL.md:26,40 (P) — tells the agent to run /mycelium-extra:init and new-analysis, both disable-model-invocation. Fix: "ask the user to type".
4. new_analysis.py:558,581 (C) — scaffolded folder is drwx------ (mkdtemp stage renamed). Fix: chmod stage to umask default.
5. verify/SKILL.md:214, verify.py:5003 (C) — `verify runs` defaults to results/, new-analysis writes outputs/. Fix: default to whichever exists.

## Tier 2: wrong results or crashes on plausible input

6. new_analysis.py:45,113,340 (C) — step handoff types: R step hands .rds to the Python step; an ipynb step hands logs/NN.ipynb to the next step. Fix: language-neutral table (.tsv/.parquet) across languages; notebooks write outputs/NN_*.
7. new_analysis.py:76-93 (C) — .living/ in a subfolder of a bigger git repo is not found: README.md instead of `<NAME>.md`, configs read from the wrong root. Fix: nearest .living/ ancestor below the git toplevel.
8. new_analysis.py:235-245 add_panels (C) — second --panels retrofit adds the stub but not the figure_map/manuscript_checks entry; same id with another kind adds a second stub. Fix: warn on missing ids; refuse a second kind.
9. gate.py:5028 dev_package_states (C) — a non-git folder inside the repo gets the repo HEAD; untracked files report dirty:false. Fix: require show-toplevel == package path; drop --untracked-files=no.
10. gate.py:237 load_config (C) — gate.json of null/"x"/[1] fails open with "unreadable"; [] silently = defaults. Fix: named "must be an object" error; honour on_error.
11. verify.py:101 read_jsonl (C) — one non-UTF-8 byte in receipts.jsonl crashes report/write/disclose/status. Fix: errors="replace".
12. verify.py:3627 (C) — dev_packages receipt field never validated; wrong types crash report and write. Fix: validate in read_jsonl.
13. verify.py:2722 (C) — first write of a second plan in a folder gives CONFORMS_WITH_GAPS ("legacy bundle"); second write CONFORMS. Fix: no marker for this hash = no saved bundle.
14. verify.py:4903 (C) — RUN.txt version "²" passes isdigit, int() crashes `runs`. Fix: re.fullmatch("[0-9]+").
15. data_contract_check.py:1433 (C) — duplicate JSON keys use the last value (can loosen min_rows). Fix: reuse reject_duplicate_json_keys.
16. data_contract_check.py:1455 (C) — --result-json into a missing dir loses the report. Fix: makedirs, print report first.
17. new-analysis §2 vs grill §0 (P) — new-analysis promises grill won't re-ask, but it never records a hoped-for claim, so grill asks again. Fix: ask the claim in §2 too.
18. grill/SKILL.md:3,8 vs :104 (C) — "make no edits / wait for approval" contradicts gate-off auto-execute. Fix: "except under gate off".
19. plan-review/SKILL.md:38 (P) — runs review_packet.py by path, which other skills say opens Mycelium's post-action cycle. Fix: stdin form or state the exemption.

## Tier 3: low (edge crashes, docs drift)

20. gate.py:5204 — gate on/off cannot toggle when gate.json is corrupt.
21. gate.py:3880 — Codex/OpenCode have no transcript_path, so /goal never ends on met/failed there (P).
22. new_analysis.py:128-143 — lucid-coder.yaml regex: non-UTF-8 traceback, packages: block overrides env:, relative paths, spaces, ~; malformed gate.json drops step_format silently.
23. analysis_report.py:179 — Snakefile.d/ dir crashes; Snakefile.bak parsed as a workflow.
24. analysis_report.py:81 — rule→script match reads only shell text; mermaid shows bare nodes for R/py/qmd/marimo steps.
25. new_analysis.py:43, run.sbatch:6 (P) — empty logs/ not tracked by git; SLURM --output path missing after clone. Fix: logs/.gitkeep.
26. verify.py:5394 — write shows a traceback on provenance ValueError.
27. verify.py:2722 — read-only report/disclose create provenance/.publish.lock.
28. verify.py:~114 — pins values unvalidated; status/stale AttributeError.
29. track_changes.py:577-600 — non-str headings TypeError; reports/x.qmd directory aborts.
30. manuscript_audit/data_contract/review_packet — RecursionError on deeply nested JSON.
31. data_contract_check.py:1452 — NUL byte in table path + --result-json traceback.
32. default_reasons.py:63 — `| - | - |` row read as a table rule; drops a default.
33. presend_check.py:66 — UTF-8 BOM hides `redactions: []` (fails safe, false rc=3).
34. gate_init.py:501 — a file named .mycelium-extra crashes init; review_packet prepare without gate.json writes state in cwd.
35. capture.py:102 — title not length-capped; huge token gives "Argument list too long".
36. report.qmd:13 — template says quarto render is gated; analysis-report says engine: markdown passes.
37. decision-status/SKILL.md:44 (P) — its questions vs grill's five-question cap undefined.
38. gate-json.md:13, state-files.md:18 — say 17 keys; table lists 18.
39. new-analysis/SKILL.md:57 — usage line lacks |marimo.
40. track-changes/SKILL.md:3 — description says read-only; it writes its report folder.
