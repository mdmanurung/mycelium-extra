# Packaging and adoption

[Back to roadmap](README.md)

Small tasks that decide whether anyone else can use the plugin.

### A1: Add a license

- **Why:** there is no LICENSE file, so by default nobody else may reuse, modify, or redistribute the code. The bundled `skills/new-analysis/templates/MYCELIUM_LICENSE` covers only the copied Mycelium template.
- **Scope:** a top-level `LICENSE` file; a `license` field in `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` if their schemas support one; one line in the README.
- **Out of scope:** relicensing third-party content; contributor agreements.
- **Depends on:** none.
- **Constraints:** must be compatible with the MIT-licensed Mycelium template the repository already redistributes.
- **Grill prompt:** `/mycelium-extra:grill Add a LICENSE to the repository. Check what the bundled Mycelium template's license requires, recommend MIT or Apache-2.0 with the trade-off (patent grant versus brevity), and list every manifest field that should name it.`
- **Acceptance:** `LICENSE` exists at the root; GitHub detects it; MYCELIUM_LICENSE stays in place for the template it covers.
- **Tests:** none.
- **Effort:** S.
- **Status:** done; the maintainer confirmed MIT and the copyright line (2026-10-04). `LICENSE` is the standard MIT text (Copyright (c) 2026 Mikhael Manurung, the year of the first commit); both `plugin.json` files gain `"license": "MIT"` (both schemas document the field); the README gains a License section that points to MYCELIUM_LICENSE, which is unchanged. GitHub detection can only be confirmed after a push.

### A2: Continuous integration

- **Why:** the tests run only by hand. The gate's Bash parsing is the code most likely to break without anyone noticing, and the Python 3.6 requirement is only checked when a 3.6 interpreter happens to be installed.
- **Scope:** a GitHub Actions workflow running `hooks/tests/test_gate.py`, each `skills/*/tests/test_*.py`, and the fixture-project tests from C1, on Python 3.6 and the newest supported Python. A separate job runs `hooks/tests/gate_diff.py` against the PR's base commit.
- **Out of scope:** linting style; publishing releases (A3).
- **Depends on:** C1.
- **Constraints:** Python 3.6 must stay in the matrix (bare `python3` on HPC systems). Actions' hosted runners no longer ship 3.6, so use a container image or a setup action that still provides it, and say which.
- **Grill prompt:** `/mycelium-extra:grill Add a GitHub Actions workflow that runs every test file by name on Python 3.6 and the newest Python, plus gate_diff.py against the base commit on pull requests. Check how the tests locate the repository and whether any need the gate disabled or a git history.`
- **Acceptance:** a PR shows green checks for both Python versions; deliberately breaking one gate decision makes `gate_diff.py` fail the PR.
- **Tests:** the workflow is the test. Record one intentionally failing run as evidence.
- **Effort:** M.
- **Status:** todo.

### A3: Changelog and tagged releases

- **Why:** the plugin is at 0.9.x, with version bumps as separate commits but no tags or release notes. Users cannot tell what an update changes before running `claude plugin update`.
- **Scope:** `CHANGELOG.md` in Keep a Changelog form, rebuilt from `git log` for 0.9.16 onward (earlier versions summarised); git tags `v0.9.x` for the versions the changelog lists; a line in `docs/development.md` (or the README's Development section) making a changelog entry part of the version-bump commit.
- **Out of scope:** automated release tooling.
- **Depends on:** none.
- **Constraints:** the version-bump rule (three manifests) stays as is; the changelog entry joins it.
- **Grill prompt:** `/mycelium-extra:grill Add CHANGELOG.md reconstructed from git log, tag the versions it covers, and extend the version-bump rule so each bump commit also adds a changelog entry. Inspect the commit history before asking me anything.`
- **Acceptance:** the changelog covers every version from 0.9.16 to the current one; each has a tag; the development rules mention the changelog.
- **Tests:** a small check that the newest changelog heading matches `version` in all three manifests (fits into A2).
- **Effort:** S.
- **Status:** in-progress. CHANGELOG.md covers 0.9.16 to 0.9.29 (earlier versions summarised) and `docs/development.md` adds the changelog to the version-bump rule. Tags are not created yet: the `git tag -a` commands are ready for the maintainer to run and push.

### A4: Repository description and topics

- **Why:** the GitHub page has no description or topics, so people looking for agent guardrails or provenance tooling will not find it.
- **Scope:** a one-line description and topics such as `claude-code`, `codex`, `llm-agents`, `reproducibility`, `provenance`, `bioinformatics`, `research-software`.
- **Out of scope:** a website or badges.
- **Depends on:** none.
- **Constraints:** none.
- **Grill prompt:** not needed; set in the GitHub repository settings.
- **Acceptance:** the description and topics show on the repository page.
- **Tests:** none.
- **Effort:** S.
- **Status:** todo (maintainer action). The description, topics, and a `gh repo edit` command are drafted; a patch cannot set them.

### A5: Check Mycelium compatibility

- **Why:** several behaviours depend on how Mycelium 0.6.0 and 0.7.2 hooks parse things (stdin scripts not counted as post-action runs, `Status` read as body text in `decisions.md`). A future Mycelium release could break them without warning.
- **Scope:** a "Tested with Mycelium" line in the docs listing known-good versions; `init` reads the installed Mycelium version (through `.mycelium/plugin-root` or the plugin manifest) and prints a plain-text notice when it is outside the tested range. No blocking.
- **Out of scope:** supporting multiple Mycelium versions with different code paths.
- **Depends on:** none (C1 makes it testable).
- **Constraints:** complement, not override: read Mycelium's files, never write them. Notice text is plain text. No SessionStart message: the check runs only inside `init`.
- **Grill prompt:** `/mycelium-extra:grill Make init report when the installed Mycelium version is outside the versions mycelium-extra was tested with. Find where the repository already depends on Mycelium version behaviour, and where init can read the installed version without running Mycelium.`
- **Acceptance:** `init` on a repository with an untested Mycelium version prints one notice naming both versions; on a tested version it prints nothing extra; with no Mycelium it says nothing.
- **Tests:** `skills/init/tests/test_gate_init.py` gains three cases (tested, untested, absent).
- **Effort:** S.
- **Status:** todo.

### A6: A worked example

- **Why:** the quick start lists the steps but never shows what a grill brief, an approval notice, or a verify report looks like. Seeing them is what convinces a researcher the friction is worth it.
- **Scope:** `docs/example.md`, one end-to-end session on the C1 fixture project: the grill prompt, the brief and plan table, the approval notice, the gated run, and the verify report, using real (not hand-written) output.
- **Out of scope:** a video or screenshots.
- **Depends on:** C1.
- **Constraints:** the transcript must come from an actual run, so it stays honest; regenerate it when output formats change.
- **Grill prompt:** `/mycelium-extra:grill Write docs/example.md as a real end-to-end transcript on the fixture project: grill, approve, run, verify. Plan how to capture the output so it can be regenerated when formats change.`
- **Acceptance:** every block in the example is real output from the fixture project; the example is linked from the README quick start.
- **Tests:** optional: a check that the statuses quoted in the example (`Plan status:`, `Verify status:`) still exist in the skills.
- **Effort:** M.
- **Status:** todo.
