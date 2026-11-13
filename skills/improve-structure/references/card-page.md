# Candidate page

The review page is a private, one-off Artifact. It is an evaluation copy for the user. The record stays in the repository (the analysis doc and, later, the grill plan). Do not write the page into the repository.

Write the page file in the scratch folder, then publish it with the Artifact tool. Follow `skills/analysis-report/references/artifact-page.md` for the page contract and the colour tokens, and the Artifact tool's own design rules. Do not add scripts for decoration.

## Layout

- Title: two to four words, for example "Structure review".
- A short header: the analysis path, the date, the scope line from step 1 (hot spots or the user's direction), and the count of scanner findings.
- One card per candidate, strongest first. No introduction paragraph.
- A last block, "Not a candidate": scanner findings you dropped after the deletion test, one line each with the reason.

## Card

| Part | Content |
|---|---|
| Title | The deepening in a few words, for example "One prepare step for the donor matrix" |
| Badge | `Strong`, `Worth exploring` or `Speculative` |
| Tag | `outputs identical` (the change can keep every output byte-identical) or `needs a plan row` (it could change a result) |
| Files | Monospaced list of scripts and notebooks |
| Problem | One sentence |
| Proposed change | One plain sentence. No function names, no signatures |
| Benefit | Up to four short bullets in leverage, locality and testability terms: "locality: the filter lives in one script", "leverage: three steps read one table", not "cleaner code" |
| Before / after | The diagram below |
| Outputs check | Which `outputs/<stem>/` tables to compare before and after, and which figures to open |

## Before and after diagram

Draw steps as boxes and `outputs/<stem>/` files as the arrows between them. Use inline SVG or a Mermaid `<pre class="mermaid">` block. Show the seams.

- Before: the leak. Mark shared-folder reads and duplicated blocks in the warning colour.
- After: the same steps with the leak gone, one box drawn thicker where work is gathered. Show the seam as a file name, not as code.
- Keep each diagram near 320 px tall so the two sit side by side on a wide screen and stack on a phone.

## Wording

Plain, short sentences. Name steps by their script stem (`02_fit`). Say "the step reads three other steps' outputs", not "high coupling". Do not claim a result is right or wrong. Structure claims cite files and lines. A claim about a result cites a saved figure you opened, or reads `unsupported: no inspected figure`.

## After the page

Give the link and ask: "Which of these would you like to explore?" Do not propose an interface. Do not start a plan. When the user picks one, the next step is `/mycelium-extra:grill`.
