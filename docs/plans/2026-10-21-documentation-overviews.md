# Documentation overview rollout

Continue the five-page pilot from `84f0ffe` in an isolated checkout; preserve
existing questions, worked examples, evidence, anchors and publication scope.

1. Add the remaining 31 page-specific SVGs and descriptions: 22 published pages
   in total, plus five repository-only guides, eight cases and the day walkthrough.
2. Check the complete set in light/dark themes, narrow layout and 200% zoom,
   including keyboard disclosures and accessibility-tree reading order. Record
   actual browser and assistive-technology availability without equating tree
   inspection with a human screen-reader session.
3. Update the deprecated action runtimes using official manifests; preserve
   test interpreter versions, triggers, permissions and the gate-diff oracle.
4. Build Sphinx, check all links/assets, verify preservation of original content,
   run affected workflow compatibility checks, and record outcomes and limits.

Static SVGs remain their editable sources. No library, audio, animation or
analysis/report runtime behavior is added by this documentation change.

## Completed scope

- All 36 learning pages now have a page-specific overview, accessible description
  and caption: 22 pages in the existing website and 14 repository-only pages.
  The publication list and navigation are unchanged.
- Added 31 SVGs and dark palettes to the five pilot SVGs. Figures distinguish
  human decisions, recorded facts and unknown evidence with wording and borders,
  not color alone. No external assets or executable SVG content are used.
- Scoped inline-code wrapping fixes narrow-page overflow without changing the
  scrolling behavior of executable examples.
- Corrected two stale explanations in `docs/day.md` and
  `docs/guides/full-workflow.md`: ordinary approved-script edits re-pin with a
  notice; changed pinned inputs and exact contracts have different requirements.
  Historical case quotations remain unchanged. Every original heading, fenced
  example and answer disclosure is preserved across all 36 pages.
- Migrated checkout/setup actions to v7 and Pages actions to v5, and pinned
  hosted runners to Ubuntu 24.04. Official action manifests were inspected for
  Node 24 support. The interpreter matrix, triggers, permissions, commands and
  gate-diff oracle are unchanged. Sources:
  [checkout](https://github.com/actions/checkout/tree/v7),
  [setup-node](https://github.com/actions/setup-node/tree/v7),
  [setup-python](https://github.com/actions/setup-python/tree/v7),
  [upload-pages-artifact](https://github.com/actions/upload-pages-artifact/tree/v5),
  [deploy-pages](https://github.com/actions/deploy-pages/tree/v5).

## Validation on 21 October 2026

Production build, with Sphinx 9.1.1 and the pinned documentation requirements:

```bash
/tmp/journal-docs/bin/python -m sphinx -b html -W --keep-going -c docs . /tmp/mycelium-doc-rollout-site
python3.12 tests/check_links.py $(git ls-files '*.md' ':!:mycelium-extra-improvements/**')
python3.12 tests/test_ci_pins.py
python3.12 hooks/tests/test_gate_diff.py
python3.12 tests/test_versions.py
git diff --check
```

The production build passed; 482 links resolved, and all four affected unit
checks passed. Parsed workflow structures were identical to the pilot after
removing only action versions and runner labels. All 36 SVGs passed passive-asset
checks, title/description checks and rendered text-bound checks. Text contrast
against each palette background exceeded 4.5:1 in both themes.

Browser evidence is retained locally under the ignored directory
`docs/plans/evidence/documentation-overviews-2026-10-21/`, including the standalone
Node scripts, exact page list, logs and screenshots. Run a saved browser harness
with the built preview directory and an output prefix; `--dark` selects dark
mode and `--zoom200` uses a real browser zoom preference. The scripts use only
Node's standard library and disposable browser profiles. Browser executable paths
are local QA prerequisites, not package dependencies.

Firefox 140.17 and Chrome 156 were exercised across all 36 pages at desktop
1280px, narrow 390px, and true 200% zoom (640 CSS pixels), in light and dark
modes: 432 page checks in total. Checks cover document overflow, loaded diagrams,
image descriptions, collapsed answers, keyboard activation and visible focus.
Chrome accessibility-tree checks cover the exposed image name, heading/image
reading order and disclosure state. All 36 SVGs were also checked directly in
both browsers for canvas clipping and padding inside boxes. Contact sheets of
all figures and representative actual narrow/dark/zoom pages were inspected.

The repository-only pages were built in a temporary preview configuration that
adds those 14 pages. That preview alone suppresses missing cross-reference and
not-included warnings for links to deliberately unpublished reference pages;
all source links were checked separately. No suppression was added to the
production configuration.

No screen-reader application was available, so a human spoken-assistive-
technology walkthrough remains unchecked. Browser accessibility-tree and
keyboard results are narrower evidence. New hosted action execution and Pages
publication remain pending a separately requested push; local builds do not
publish. Full runtime suites were not repeated for these static documentation
changes; the existing pilot's hosted Python/Node CI passed. Gate behavior,
approvals, verification, Journal collection and researcher notes were untouched.
