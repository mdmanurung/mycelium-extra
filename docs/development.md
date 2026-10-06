# Development

[Back to README](../README.md)

Mycelium Extra sits between a plan and its execution. A small change to command
recognition or a hook payload can change which runs are allowed, so development
starts with the behavior you intend to change and the checks that demonstrate
it. The shared gate should keep the same meaning in Claude Code and Codex.

## Testing a change

Run the affected skill's tests and the gate tests first:

```bash
python3 skills/<skill>/tests/test_<name>.py
python3 hooks/tests/test_gate.py
```

Then run `python3 tests/test_end_to_end.py` on the fixture project (about two
minutes) and `python3 tests/test_fixture_data.py`. The ablations in
`python3 tests/e2e/ablate.py` remove individual guards to check that the defect
cases actually depend on them. See the [fixture design](design/c1-fixture-project.md).

`python3 tests/test_versions.py` checks that the three manifests and the newest `CHANGELOG.md` heading name the same version, and `python3 tests/check_links.py $(git ls-files '*.md')` that every relative link and anchor resolves.

CI (`.github/workflows/ci.yml`) runs all of the above on every push to `main` and every pull request, in the official `python:3.6-bullseye` image under `LC_ALL=C` and in `python:3.14-bookworm`, since hosted runners no longer ship 3.6. On a pull request it also runs `gate_diff.py --base` against the PR's base commit, so an intended gate change shows as a red check to explain in the PR.

Before changing `hooks/gate.py`, also run `python3 hooks/tests/gate_diff.py`: it sends the same events to the committed gate and the working tree and must report every case identical, except the decisions you meant to change.

## Python compatibility and versions

Hooks call bare `python3`, which is 3.6 on some HPC systems, so keep every script 3.6-compatible; the gate tests compile them all under `python3.6` when it is installed.

Bump `version` in `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json` together, so `claude plugin update` picks up the change. The same commit adds a [CHANGELOG.md](../CHANGELOG.md) entry for the new version.

## Cross-host checks

Passing a Python test does not show that a host loaded the plugin or dispatched
its hooks. Check both layers: the shared behavior in the test suite, and the
installed plugin in a real host session.

`python3 hooks/tests/test_codex_gate.py` checks the Codex entrypoint's approval
flow, receipts, missing exit status, and state protection for patches and moves.
`hooks/hooks.json` is Claude's configuration; the Codex manifest points to
`hooks/codex.json`. Keep host decoding at the launcher boundary and reuse the
shared gate. Codex shell tools expose `Bash` and `tool_input.command` to hooks.
Do not assume a Codex post event means exit 0.

Validate Claude's marketplace and plugin separately:

```bash
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
```

For Codex, install the checkout in a disposable `CODEX_HOME`, check the cached
files against the source, and test discovery. Real host tests need trusted,
enabled hooks; invoking the Python launcher alone does not prove dispatch.

### Validated on 2026-10-06

Version 0.9.43 was checked with Claude Code 2.1.291 and Codex CLI 0.160.0.
Both live hosts denied an unapproved fixture run, registered a plan through
Stop, accepted its hash through UserPromptSubmit in the same session, allowed
the approved run, and wrote a receipt. Claude's receipt recorded exit 0;
Codex's recorded `unknown`, matching its missing hook exit metadata. A failed
Codex run also left an `unknown` receipt rather than a success claim.

Codex discovered nine skills and four hooks without hook configuration errors;
62 installed hook and skill files matched the source. All 14 test files passed
on Python 3.6.8; the Python 3.12.14 suite and corrected heading checks passed
as well. Optional-tool cases retained their skips. Gate comparison was 160/160
identical and all three ablations caught their missing guards. The Sphinx build
had no warnings; Markdown links and generated HTML paths had no broken targets.
These checks validate the local candidate, not a published installation or a
GitHub Pages deployment.

## Documentation website

The website and repository use the same Markdown pages. You can improve a
guide without maintaining a second copy, and Sphinx checks the links when it
builds the site.

Use Python 3.12 for the website tooling; the plugin still supports Python 3.6.

```bash
python3.12 -m venv /tmp/mycelium-extra-docs
/tmp/mycelium-extra-docs/bin/python -m pip install -r docs/requirements.txt
/tmp/mycelium-extra-docs/bin/python -m sphinx -b html -W --keep-going -c docs . docs/_build/html
/tmp/mycelium-extra-docs/bin/python -m http.server 8000 --directory docs/_build/html
```

Open `http://localhost:8000/`. The build treats warnings as errors and checks
internal document links. The configuration uses an explicit list of user guides
and the run-plan reference. Developer instructions, roadmap, changelog, design notes, and the
repository README are excluded from the website and its search index.
Generated HTML is ignored by Git.

The Documentation workflow builds every pull request and publishes pushes to
`main`. In GitHub repository **Settings → Pages**, choose **GitHub Actions**
as the source before the first deployment. The published URL will be
`https://mdmanurung.github.io/mycelium-extra/`. A local build does not publish it.
See [Sphinx's deployment guide](https://www.sphinx-doc.org/en/master/tutorial/deploying.html).
