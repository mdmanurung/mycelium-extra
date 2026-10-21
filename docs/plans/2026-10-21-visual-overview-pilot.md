# Documentation visual overview pilot

Five pages now pair an opening diagram with a plain-language description:

- First plan: six steps from installation to checking recorded evidence.
- E01: conversational agreement versus accepted plan approval.
- E03: the narrow correction plan and its required magnitude check.
- E07: planned and recorded as independent questions.
- Track changes: Journal overview, selected item, evidence and persistent coverage.

The editable sources are five static SVGs in `docs/figures/`; they need no build
generator, network resource or runtime dependency. Each has a title, description
and visible text labels, with image alt text and a caption in its page. E01,
E03 and E07 add native HTML disclosures for checking understanding. They store
no decisions and invoke no tool. Original questions, examples and evidence remain.
The figures are labelled schematics; none is a captured approval or a new result.

## Validation on 2026-10-21

- Warning-as-error Sphinx build passed; all 451 Markdown links resolved.
- SVG parsing and asset inspection found no scripts, event handlers, embedded
  images, foreign objects or external links. All five assets reach the built site.
- Real Firefox checked all five built pages at 1280px, 390px and actual 200%
  browser zoom (DPR 2, 640 CSS pixels). Image loading, alt text, initially closed
  disclosures, native Tab/Enter operation, visible focus and absence of page-wide
  horizontal overflow passed. Rendered screenshots were visually inspected.
- Two existing long inline commands on the Journal example became fenced blocks
  after narrow inspection exposed page overflow. Commands now scroll locally.
- This is documentation only: no gate, verifier, journal data or approval behavior
  changed. Runtime suites were not repeated for static assets and explanatory text.

Firefox light-theme checks do not replace testing other browsers, a screen reader
or dark mode. No narration, animation or remote interactive service was added.
The remaining pages are covered by the separate page-by-page visual proposal,
not implemented by this five-page pilot.
