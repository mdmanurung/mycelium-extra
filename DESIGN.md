---
name: Mycelium Extra
description: Quiet, cool-paper design for the plan, journal and report pages Mycelium Extra writes
colors:
  paper: "#f9fbfd"
  paper-2: "#edf1f4"
  ink: "#111921"
  ink-2: "#4d5660"
  rule: "#d9dfe3"
  rule-strong: "#bbc2c7"
  accent: "#00696f"
  pass: "#277a55"
  stale: "#b46d10"
  gap: "#914a8c"
  fail: "#b2392b"
  routine: "#81878c"
  add: "#daf9e7"
  del: "#ffe8e4"
  paper-dark: "#0e1216"
  paper-2-dark: "#161b20"
  ink-dark: "#e3e9ed"
  ink-2-dark: "#9ea6ab"
  rule-dark: "#292f34"
  rule-strong-dark: "#42494f"
  accent-dark: "#64c3c8"
  pass-dark: "#75c59b"
  stale-dark: "#efb062"
  gap-dark: "#d997d2"
  fail-dark: "#f28979"
  routine-dark: "#81878c"
  add-dark: "#0e3020"
  del-dark: "#3e1e1c"
typography:
  heading:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontWeight: 650
    lineHeight: 1.3
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontFamily: "ui-monospace, SF Mono, Cascadia Mono, Menlo, Consolas, monospace"
    fontSize: "0.86em"
rounded:
  sm: "4px"
  md: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
components:
  status-pill:
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  focal-node:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
---

# Mycelium Extra design

## Overview

These pages are for reading and checking, not persuading. A researcher opens a journal, a track-changes review or an analysis report to find out what ran, what was approved and what is still a gap. The design is quiet so the evidence stands out: cool paper, one teal accent, and status shown as a word in a tinted pill.

Picked on 2026-11-04 from three rendered options. It takes option B's colours and pills, and option A's system fonts.

Where the tokens live. `tests/test_design_tokens.py` checks that each copy matches this file.
- `skills/track-changes/assets/viewer.css` (journal and track-changes viewer), as CSS custom properties.
- `skills/new-analysis/templates/report.scss` and `report-dark.scss` (Quarto report theme), as SCSS variables.
- `docs/scenario/make_figures.py` (docs figures), the neutrals and status colours only.

## Colors

Each token has a light value and a `-dark` value. Pages define the light values on `:root` and redefine them for `prefers-color-scheme: dark` and for `[data-theme="dark"]`.

- **paper / paper-2**: page ground and raised surfaces such as panels, code blocks and diagram nodes.
- **ink / ink-2**: body text, and secondary text such as captions, paths and inspection lines.
- **rule / rule-strong**: row dividers, and frame or input borders.
- **accent**: one teal for the current selection, links, focus and the one focal diagram node, usually the approval gate. Use it nowhere else.
- **pass / stale / gap / fail / routine**: verify and journal states. The viewer's older names map onto them: `--st-authorized` is pass, `--st-attention` is stale, `--st-routine` is routine.
- **add / del**: diff backgrounds in track-changes.

**Data colours are separate.** Figures use the Okabe-Ito palette (`#0072B2`, `#E69F00`, `#009E73`, `#CC79A7`, `#D55E00`, `#56B4E9`), which is colour-blind safe. The UI accent and status tokens are never used as data series, so a teal mark always means the UI.

## Typography

System fonts only. The viewer is an offline file whose policy blocks web fonts, and the report must look the same with no network.
- **heading**: system sans, weight 650.
- **body**: system sans, 15px, line height 1.5, about 65 characters per line in reading pages.
- **mono**: paths, hashes, code, run labels, and digits that line up in columns (`tabular-nums`).

## Layout

- Reading pages (report, journal detail) run in a single column of about 920px or less. The viewer's review list and detail split into two columns above 750px and stack below it.
- Spacing steps: 4, 8, 16, 24, 40px. Lay out sibling groups with `gap`, not per-element margins.
- Wide tables, code and diagrams scroll inside their own container. The page never scrolls sideways.

## Elevation & Depth

Flat. Separation comes from `rule` lines and the `paper-2` surface, not shadows.

## Shapes

`sm` 4px for nodes and inputs, `md` 6px for frames and buttons, `pill` for status pills.

## Components

- **status-pill**: the state word (pass, gap, fail, stale, routine) on a 16% tint of its state colour, with a 55% inset ring of the same colour, and the text in `ink`. The word is always present, so colour never carries the meaning alone.
- **row**: mono path, then the status pill. The reason goes below in `ink-2`.
- **focal-node**: the one accent-filled node in a diagram. Every other node is `paper-2` with a `rule-strong` border.
- **inspection line**: `ink-2`, with a 2px `rule-strong` left border, naming the inspected figure path.

## Do's and Don'ts

- Do show every state as a word. Don't rely on colour, a dot or an icon alone.
- Do keep one accent. Don't add a second highlight colour.
- Don't use gradients, glows, shadows on cards, or emoji as markers.
- Don't load web fonts or remote assets in generated pages.
- Do show "not verified" or "gap" when evidence is missing. Never style a missing check like a pass.
