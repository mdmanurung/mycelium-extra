# Artifact evaluation page: design reference

Read this before `analysis-report artifact`. The page is a one-off evaluation copy of a filled report, written in one pass. The Quarto `.qmd` and its HTML stay the record. A worked example is `tests/fixtures/artifact/good_page.html`.

Rules taken from impeccable's Read mode (Apache-2.0, `reference/mode-read.md`) are marked (impeccable). The tokens come from the repo's `DESIGN.md`.

## Page contract

The page file lives at `.mycelium-extra/artifacts/<name>.html` at the repository root, outside `reports/`. The host wraps the page in its own skeleton. Write a fragment, not a document.

- No `<!DOCTYPE>`, `<html>`, `<head>` or `<body>` tags.
- Start with `<title>`: a short name of two to four words, not a summary. Put it in the first 8 KB.
- Next line: `<meta name="claude:viewport-fit-sides" content="cover">`.
- Every colour is a token. Define light on bare `:root`. Redefine dark under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { ... } }` and again under `:root[data-theme="dark"]`. Put `color-scheme: light` and `color-scheme: dark` beside them.
- Give `body` an explicit background from a token. Style `body` with a CSS rule, since the page has no `<body>` tag of its own.
- Prefer no scripts. If one is needed, load it only from `cdnjs.cloudflare.com`, `cdn.jsdelivr.net/npm`, `unpkg.com`, `cdn.tailwindcss.com` or `code.jquery.com`, pinned to an exact version.
- Stylesheets come only from `fonts.googleapis.com`. Use system fonts here, so none are needed.
- At most 16 MB, data URIs included. Data URIs grow a figure by about 33%.
- Works at 400px wide with no horizontal page scroll. Wide tables and code scroll inside their own box.
- Side gutter: `padding-left: max(16px, env(safe-area-inset-left, 0px))`, and the same for the right with `safe-area-inset-right`.
- No print button, no download link, no `alert` or `confirm`.
- Mermaid is `<pre class="mermaid">...</pre>`. The host draws it. Load no library.

## Tokens

Paste this block unchanged at the top of the page `<style>`. Add no colour that is not in it. Figure pixels keep their own colours.

```css
:root {
  color-scheme: light;
  --paper: #f9fbfd; --paper-2: #edf1f4;
  --ink: #111921; --ink-2: #4d5660;
  --rule: #d9dfe3; --rule-strong: #bbc2c7;
  --accent: #00696f;
  --pass: #277a55; --stale: #b46d10; --gap: #914a8c; --fail: #b2392b; --routine: #81878c;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --paper: #0e1216; --paper-2: #161b20;
    --ink: #e3e9ed; --ink-2: #9ea6ab;
    --rule: #292f34; --rule-strong: #42494f;
    --accent: #64c3c8;
    --pass: #75c59b; --stale: #efb062; --gap: #d997d2; --fail: #f28979; --routine: #81878c;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #0e1216; --paper-2: #161b20;
  --ink: #e3e9ed; --ink-2: #9ea6ab;
  --rule: #292f34; --rule-strong: #42494f;
  --accent: #64c3c8;
  --pass: #75c59b; --stale: #efb062; --gap: #d997d2; --fail: #f28979; --routine: #81878c;
}
body { background: var(--paper); color: var(--ink); margin: 0;
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
```

Type and shape. Headings weight 650, line height 1.3. Mono is `ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace` at `0.86em`, for paths, hashes, run labels and digits (`font-variant-numeric: tabular-nums`). Radius 4px for boxes, 6px for frames, 999px for pills. Spacing steps 4, 8, 16, 24, 40px. No shadows, gradients or emoji.

## Read-mode rules

The reader came to judge whether the run answered the question. The page is a document first.

- Figures are large. A figure takes the full column width (`max-width: 100%; height: auto`), above its conclusion's caption. Never put two figures side by side at phone width. (impeccable: the column stays calm and the evidence is set in standard forms.)
- One column, about 920px wide at most, about 65 characters per line in prose (impeccable: a real measure, a reading face, real contrast).
- Wayfinding: a short in-page list of links to each question, under the banner. No tabs, no script.
- One accent (`--accent`) for links, focus and the banner rule. Use it nowhere else. Never use it for data.
- Status is a word in a pill: `pass`, `gap`, `fail`, `stale` or `not verified`, mapped from `verify` as in the status table of `docs/concepts/analysis-layout.md`: `CONFORMS` is pass; `CONFORMS_WITH_GAPS` is gap; `DOES_NOT_CONFORM` is fail; a `stale` finding is stale; no `provenance/` entry is not verified. The pill is the word on a 16% tint of its state colour with a 55% inset ring, text in `--ink`. For example `background: color-mix(in srgb, var(--pass) 16%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--pass) 55%, transparent)`. A missing check is never styled like a pass.
- Contrast: body text `--ink`, captions and paths `--ink-2`. Rules and borders use `--rule` and `--rule-strong`.
- Each figure has an alt text and a caption that names its source file.

## Order of the page

1. Banner (see below).
2. **Answer in brief**: one line per question, copied from the report's Overview.
3. One section per question, in the plan's order: the question, the figure, the conclusion with its status pill, then the inspection line. A null or adverse result gets its section too.
4. **Open items** and **Not verified**: what stays unresolved, and each conclusion marked `unsupported`, `not inspected` or `gap`.
5. Folded last, each in `<details>`: **Methods quotes** (the report's code excerpts, and the step diagram as `<pre class="mermaid">`) and **Reproducibility** (the run commands).

## Banner

The first element after the style. It names, as text:

- the run label (the newest `logs/CHANGES.md` heading; for a legacy run, `run:` in the current run's `RUN.txt`, else the run folder name);
- the plan hash;
- the `.qmd` path with its short hash, in `<code class="hash">`;
- the words `Evaluation copy. The record is reports/<name>.html`;
- `verified` or `not verified` as a status pill.

Mark the element `data-banner`. The banner is one flat element: no nested elements of the same tag (the check ends it at the first closing tag, so a `<div>` inside a `<div data-banner>` hides the rest). Put each hash in `<code class="hash">`. The number check skips those hashes.

## Content rules

- Every number, conclusion and figure comes from the filled `.qmd`, the numbers file (`numbers(folder, run)`) or a cited PNG. Add none.
- Copy a number as written in the `.qmd`. Do not round, convert or compute a new one (no percentages, sums or fold changes the report does not state).
