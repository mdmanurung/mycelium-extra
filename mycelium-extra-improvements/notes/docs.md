# docs workstream (branch docs-quick-wins, base 1db67c1)

## Commits (6; patches in patches/)
1. 24469e4 docs: split the README into a landing page plus docs/ -- T0, with B1 folded in (roadmap B1: "do it inside T0 if T0 lands first"). Draft from shared/t0-readme-restructure rebased onto 3a11123: Mermaid diagram + its two sentences kept on the landing page; restored three things the draft had changed/dropped vs the current README ("Install the plugin for all your projects", plan-review's consent sentence, verify's dated history/limit sentence kept verbatim -- moving it is B2, not mine). Added a short "## init" entry in docs/skills.md (init had no section; the draft README said "eight skills"). Statuses: T0 done, B1 done.
2. dc28a72 docs(handoff): point the dev rules at docs/development.md -- B3. README.md:236 was already stale before T0 (it pointed at a receipt bullet). Status done.
3. 9a96fd1 docs: say in the summary table that plan-review sends a packet off the machine -- B4 (Writes cell). Status done.
4. 30241f7 docs: add an MIT license -- A1. LICENSE = upstream MIT text, "Copyright (c) 2026 Mikhael Dito Manurung"; "license": "MIT" in .claude-plugin/plugin.json and .codex-plugin/plugin.json (both schemas document it: code.claude.com/docs/en/plugins-reference; openai/codex plugin-json-spec.md; upstream Mycelium's codex manifest uses it). README gets a License section pointing to MYCELIUM_LICENSE, which is unchanged (it already says what it covers). Version lines untouched. Status done pending maintainer confirmation.
5. e32dabb docs: add a changelog and make it part of the version bump -- A3. CHANGELOG.md (Keep a Changelog): Unreleased (this branch's docs work only), 0.9.29 (grill checklist, diagram, roadmap, design doc, HANDOFF), 0.9.28..0.9.16 one entry each from git log, 0.7.0-0.9.15 summarised. docs/development.md: bump commit adds a changelog entry. Status in-progress (tags not created).
6. 2f98081 docs(roadmap): record that A4 is drafted and awaits the maintainer -- A4 status only.

## Checks run
- Content preservation (tools/check_preserve.py OLD_README README.md docs/*.md): 599 units of the 3a11123/1db67c1 README (43 headings, 57 table cells, 34 code lines incl. the whole Mermaid block, 274 sentences, 191 inline-code tokens). Missing: 2, both the intended B1 removal (the "In scale" sentence and its `analysis/*/docs/` token). Same check of the raw draft against the current README: 26 missing (diagram + 3 rewordings) -> all fixed.
- Links (tools/check_links.py, GitHub slug rules, README.md HANDOFF.md CHANGELOG.md docs/*.md): 14 links, 0 broken.
- Negative tests: deleting the last Limits bullet makes check_preserve report it; changing #limits to #limitz makes check_links fail (1 broken).
- Full suite before and after (env -u CONDA_* ... per COMMON.md): all 8 files OK both times (test_gate.py OK, skipped=1 = no python3.6). No test reads README content; test_gate.py reads .codex-plugin/plugin.json "hooks" only, still {}.
- Both plugin.json files parse (python3 -m json.tool). README is 108 lines (target ~120).
- rg -n "In scale" README.md docs/ still matches docs/roadmap/02-docs-hygiene.md (B1's own quote); nothing else.

## Maintainer decisions needed
- License: MIT chosen (brevity; compatible with bundled MIT Mycelium template; Apache-2.0 would add a patent grant). Confirm.
- Copyright line: every commit is dated 2026 (first commit 2026-09-29), so the line is "Copyright (c) 2026", not 2025-2026 as briefed. Name "Mikhael Dito Manurung" differs from the manifests' author "Mikhael Manurung"; pick one.
- marketplace.json plugin entry also accepts "license"; not added (outside ownership list).
- Tags (A3) -- run after merge and push with `git push origin --tags` (shas are the bump commits on main/improvements):
    git tag -a v0.9.16 95e1bc8 -m "v0.9.16"
    git tag -a v0.9.17 291408c -m "v0.9.17"
    git tag -a v0.9.18 221287b -m "v0.9.18"
    git tag -a v0.9.19 b7c6517 -m "v0.9.19"
    git tag -a v0.9.20 d64a8ad -m "v0.9.20"
    git tag -a v0.9.21 ac20fe6 -m "v0.9.21"
    git tag -a v0.9.22 16ecf8d -m "v0.9.22"
    git tag -a v0.9.23 2fb9a08 -m "v0.9.23"
    git tag -a v0.9.24 58e41f3 -m "v0.9.24"
    git tag -a v0.9.25 16af0a1 -m "v0.9.25"
    git tag -a v0.9.26 c2ea6d1 -m "v0.9.26"
    git tag -a v0.9.27 3b1073d -m "v0.9.27"
    git tag -a v0.9.28 6f2eddb -m "v0.9.28"
    git tag -a v0.9.29 4f5ab08 -m "v0.9.29"   # subject is just "chore: bump version"
    git tag -a v0.9.30 49f9154 -m "v0.9.30"
    git tag -a v0.9.31 573fbdb -m "v0.9.31"
  The Unreleased section becomes the next version's entry at the next bump.
- A4 description: "Planning, approval gate, and provenance checks for AI-agent analysis work; complements Mycelium in Claude Code and Codex."
  Topics: claude-code, codex, llm-agents, reproducibility, provenance, bioinformatics, research-software, mycelium, ai-agents
      gh repo edit mdmanurung/mycelium-extra --description "Planning, approval gate, and provenance checks for AI-agent analysis work; complements Mycelium in Claude Code and Codex." --add-topic claude-code --add-topic codex --add-topic llm-agents --add-topic reproducibility --add-topic provenance --add-topic bioinformatics --add-topic research-software --add-topic mycelium --add-topic ai-agents

## Deviations / open items / limitations
- B1 folded into T0 (6 commits, not 7), as the roadmap directs.
- Other HANDOFF.md path:line pointers point outside the repo: mycelium-health.sh:482 is line 486 in Mycelium 0.8.1 (482 may match the installed 0.7.x); _engine.py:125 is scilintr. Left as is (B3 scope is the stale line only).
- B2 (move the dated verify history to the changelog) not done; it is now unblocked by A3.
- The checkers are not committed (docs/tests/ is outside my ownership); A2 can adopt them from tools/. A3's "newest changelog heading matches manifests" test is not written: the newest heading is [Unreleased] until the next bump.
- GitHub license detection can only be confirmed after a push. Files outside ownership touched: docs/roadmap Status lines only.
- docs/ pages' changes from other workstreams (verify, gate, data-contract-check, plan-review) are not documented here; their merges must edit docs/skills.md / docs/approval-gate.md instead of README.md (patch conflicts likely if they edit README.md).
