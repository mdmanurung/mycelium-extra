# gate-verify (branch gate-verify-fixes): NOTES

Status: PARTIAL. Commit 0 and E2 done. E3 (a-d) NOT started (ran out of iteration budget). E3 Status line left `todo`.

## Commits (base 1db67c1)
1. `test(verify): scrub host environment in verify tests` - test_verify.py gets `hermetic(test)` called from setUp:
   snapshots os.environ (restored by addCleanup, which runs last), pops gate.HOOK_ENV keys + CLAUDE_CODE_SESSION_ID,
   sets HOME to a fresh temp dir (verify reads ~/.conda/environments.txt and ~/.claude|.codex/plugins). Every
   subprocess (gate hooks, verify) inherits it. hooks/tests/test_gate.py GateTest.setUp does the same (the post hook
   copies CONDA_PREFIX etc. into receipts' hook_env; it did not fail, but leaked host values). Other skill tests read no
   env/HOME (grep), left alone. gate_diff.py passes the same env to old and new gates, so it was left alone.
2. `fix(gate): pass state-folder mentions that only name text (E2)` - hooks/gate.py:
   - names_state: a string literal that only reaches the content argument of `.write/.writelines/.write_text/.write_bytes`
     through "pure" calls (join, getcwd, abspath, realpath, normpath, relpath, dirname, basename, expanduser, str, repr,
     format) is text (new `written_text`). Any other call in between (e.g. `open(...).read()`) stops the exemption.
   - Python that the running interpreter cannot parse (only for python* runners) is scanned by stdlib `tokenize` string
     tokens (`string_literals`, comments ignored, same path/shell predicate as the AST path); if it does not tokenize, or
     the runner is not Python (R, perl), the any-mention rule still applies.
   - `sed -i` with no -e/-f/--expression/--file: first positional (the script) is no longer treated as a file.
   - Roadmap E2 Status set to done.
   Tests: `test_state_folder_named_only_in_text_passes` (3 allows + 3 twins + 3 extra denies),
   `test_python_that_does_not_parse_is_scanned_by_tokens` (calls gate.names_state directly with a source that fails
   compile on 3.11, simulating 3.8+ syntax on 3.6).

## Checks run
- Baseline (1db67c1) suite without scrub: test_verify FAILED (failures=3), all else OK. With `env -u ...`: all OK.
- After commit 1, no scrub: all 8 test files OK (test_gate skipped=1: no python3.6).
- After commit 2, no scrub and with `env -u ...` scrub: all 8 OK both ways.
- 3.6 grammar (`ast.parse(..., feature_version=(3,6))`): gate.py, test_gate.py, test_verify.py OK.
- Probe (cases from the brief, script kept privately; reproduce with the commands below):
  before: FP1 os.path.join('x',...) DENY, FP2 os.getcwd() DENY, FP3 sed backtick DENY; echo/walrus heredoc PASS;
  twins (echo > .mycelium-extra/x.json, python open(join('.mycelium-extra','x.json'),'w'), join(getcwd,...,'gate.json'),
  sed -i on .mycelium-extra/gate.json incl. backtick script, walrus heredoc writing gate.json) all DENY.
  after: FP1/FP2/FP3 PASS; every twin still DENY. These are the only decisions that changed.
- gate_diff.py after (base = commit 1, whose gate.py == 1db67c1): `148/148 identical`. The built-in scenarios and
  fuzz do not contain the E2 shapes, so no listed case changed; the three intended flips are shown by the probe and the
  new tests. (I did not add the E2 commands as gate_diff scenarios; worth doing.)
- Negative test: old gate.py with the new tests -> test_state_folder_named_only_in_text_passes FAIL and
  test_python_that_does_not_parse_is_scanned_by_tokens ERROR (no string_literals / python kwarg), for both GateTest and
  LauncherTest. Restored, suite OK. (Revert granularity: whole fix, not per sub-case.)

## Deviations / limitations
- HANDOFF.md not edited (brief preferred leaving it); roadmap says to remove the E2 item from HANDOFF.md line 51 when shipped - parent should do this at merge.
- Token-scan fallback applies only to python* runner heads; a genuinely broken Python script with the folder only in a
  comment now passes instead of denying (intended by roadmap scope).
- The `.write()` exemption is syntactic: a literal assigned to a variable first, then written, still denies (conservative).

## Not done: E3 (needs a follow-up workstream)
Findings to save time:
- (a) gate.py launch_details: for `--wrap`, the inner run is analysed by analyse_command with virtual_cwd = hook cwd
  (analyse_command recurses on `wrap:` payloads with `virtual_cwd`); fix = resolve `--chdir/-D` value from the sbatch
  tokens and pass it as cwd for the wrap payload (both in analyse_command and on_post).
- (b) It is verify-side: verify.py snakemake_records builds "command" from shellcmd + code + all `input` entries, and
  `mentions()` matches planned paths against it, so any rule input counts as a run. Fix: drop `input`; for `script:`/
  `notebook:` rules shellcmd is null and `code` is base64 of a pickled code object, so decode it and match the script
  constant (relative to the Snakefile dir). Test helper `snakemake_record` writes `code: None`. Existing test
  test_steps_inside_a_snakemake_wrapper relies on expanded shellcmd, which would keep passing.
- (c) gate.py exit_status returns None for string responses; record "unknown" there (receipt schema change: verify
  test_sbatch_receipt asserts None; verify.py ~line 660 `"ran" if code == 0 else "ran (exit status not recorded)"`
  needs a `report.add("gap", ...)`). Note sbatch receipts' exit status is the submit, not the job.
- (d) Codex: .codex-plugin/plugin.json has `"hooks": {}`, so under Codex the gate's prompt hook never writes
  approvals at all; approval records carry no host field. Maintainer decision needed: what marks a "plan approved
  under Codex" (e.g. an approval written by a skill rather than the hook, or a `host` field added by the hook).
