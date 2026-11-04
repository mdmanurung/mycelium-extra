"""Static slop-lint for the HTML pages Mycelium Extra generates.

Run: python3 tests/slop_lint.py <file.html> [...]   (exit 1 when there are findings)
Use: from slop_lint import lint; lint(html_text) -> [(rule_id, line, message), ...]

Stdlib only, Python 3.9+, no browser and no Node. It reads HTML and CSS as text, so it
checks only what text can show. DESIGN.md at the repo root holds the tokens it checks against.

The ideas come from two MIT-licensed rule sets. No code or prose is copied.
- taste-skill, `design-taste-frontend/scripts/lib/rules.mjs`,
  Copyright (c) 2026 Leonxlnx. MIT License.
- Hallmark, `scripts/sloplint-render.mjs` and `scripts/sloplint.mjs`,
  Copyright (c) 2026 Hallmark contributors. MIT License.
Rules that cite DESIGN.md come from this repo's own design file.

Line numbers in the source comments refer to the files as read on 2026-11-04.
"""

import html as _html
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data series colours that DESIGN.md allows in figures (Okabe-Ito).
OKABE_ITO = {"#0072b2", "#e69f00", "#009e73", "#cc79a7", "#d55e00", "#56b4e9"}
# Named families in the DESIGN.md stacks (typography.heading/body/mono).
DESIGN_FAMILIES = {"segoe ui", "roboto", "sf mono", "cascadia mono", "menlo", "consolas",
                   "-apple-system"}
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
                    "ui-monospace", "ui-serif", "ui-sans-serif", "ui-rounded", "math",
                    "emoji", "inherit", "initial", "unset"}
STATUS_CLASS = re.compile(r"(?:^|[\s_-])(?:pill|badge|status|dot|st)(?:$|[\s_-])|^st-", re.I)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕⬛⬜️⃣]")
COLOUR_FN = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


RULES = ("gradient", "gradient-text", "text-shadow", "box-shadow", "glass", "micro-label",
         "important", "font-face", "font-count", "font-stacks", "remote-asset", "emoji",
         "pure-black-white", "hardcoded-colour", "token-not-in-design", "status-no-word")


def design_palette(path=None):
    """Hex colours listed under `colors:` in DESIGN.md, lower-case, plus Okabe-Ito."""
    path = path or os.path.join(REPO, "DESIGN.md")
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return set()
    front = text.split("---")[1] if text.startswith("---") else ""
    block = front.split("colors:")[-1].split("\ntypography:")[0]
    return set(re.findall(r'"(#[0-9a-fA-F]{6})"', block.lower())) | OKABE_ITO


# ---- text and CSS helpers -------------------------------------------------------------

def _blank(match):
    """Replace text with spaces but keep newlines, so line numbers stay true."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _prepare(text):
    """Blank JSON data scripts and CSS/HTML comments; return the cleaned text."""
    text = re.sub(r"(?is)<script[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>.*?</script>",
                  _blank, text)
    text = re.sub(r"(?s)<!--.*?-->", _blank, text)
    return text


def _line(text, offset):
    return text.count("\n", 0, offset) + 1


def _split_top(value, sep):
    """Split on `sep` outside parentheses and quotes."""
    parts, depth, quote, cur = [], 0, "", []
    for ch in value:
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    return parts


def _decls(body, base):
    """Yield (prop, value, offset) for each declaration in a rule body."""
    pos = 0
    for part in _split_top(body, ";"):
        if ":" in part:
            prop, _, value = part.partition(":")
            if prop.strip():
                yield prop.strip().lower(), value.strip(), base + pos + len(part) - len(part.lstrip())
        pos += len(part) + 1


def parse_css(css, start_line=1):
    """Return rules: dicts with selector, ctx (at-rule headers) and decls (prop, value, line)."""
    rules, i, n = [], 0, len(css)

    def scan_block(open_at):
        depth, j, quote = 0, open_at, ""
        while j < n:
            ch = css[j]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return n

    def walk(lo, hi, ctx):
        k, head_start, quote = lo, lo, ""
        while k < hi:
            ch = css[k]
            if quote:
                if ch == quote:
                    quote = ""
            elif ch in "\"'":
                quote = ch
            elif ch == ";":
                head_start = k + 1
            elif ch == "{":
                head = css[head_start:k].strip()
                end = min(scan_block(k), hi)
                inner = (k + 1, end)
                if head.startswith("@") and not head.lower().startswith("@font-face"):
                    walk(inner[0], inner[1], ctx + (head,))
                else:
                    rules.append({
                        "selector": head, "ctx": ctx,
                        "decls": [(p, v, start_line + css.count("\n", 0, o))
                                  for p, v, o in _decls(css[inner[0]:inner[1]], inner[0])],
                        "line": start_line + css.count("\n", 0, head_start + len(css[head_start:k]) - len(css[head_start:k].lstrip())),
                    })
                k = end
                head_start = end + 1
            k += 1

    walk(0, n, ())
    return rules


def extract_css(text):
    """Rules from <style> blocks and style="" attributes, with true line numbers."""
    rules = []
    for m in re.finditer(r"(?is)<style[^>]*>(.*?)</style>", text):
        body = re.sub(r"(?s)/\*.*?\*/", _blank, m.group(1))
        rules += parse_css(body, _line(text, m.start(1)))
    for m in re.finditer(r"""(?is)\sstyle\s*=\s*("([^"]*)"|'([^']*)')""", text):
        body = m.group(2) if m.group(2) is not None else m.group(3)
        line = _line(text, m.start())
        rules.append({"selector": 'style=""', "ctx": (), "line": line,
                      "decls": [(p, v, line) for p, v, _ in _decls(body, 0)]})
    return rules


def _norm_hex(h):
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h[:7]


# ---- rules ------------------------------------------------------------------------------

def lint(html_text, palette=None):
    """Return a sorted list of (rule_id, line, message) for one HTML page."""
    palette = design_palette() if palette is None else palette
    text = _prepare(html_text)
    # CSS comments inside <style> are blanked by extract_css; scripts keep their own text.
    css = extract_css(text)
    out = []

    def add(rule, line, msg):
        out.append((rule, line, msg))

    stacks, outside = {}, {}
    for rule in css:
        sel = rule["selector"]
        # DESIGN.md "Don't load web fonts"; hallmark sloplint.mjs:160 parses @font-face rules.
        if sel.lower().startswith("@font-face"):
            add("font-face", rule["line"], "@font-face loads a web font; use the system stacks")
        decls = rule["decls"]
        props = {p: v for p, v, _ in decls}
        reduced = any("prefers-reduced-motion" in c or "print" in c for c in rule["ctx"])
        for prop, value, line in decls:
            low = value.lower()
            # taste rules.mjs:68 'gradient' (FAIL); hallmark sloplint-render.mjs:572; DESIGN.md.
            if "gradient(" in low:
                add("gradient", line, f"{prop}: gradient fill in {sel or 'rule'}; use a flat colour")
                # taste rules.mjs:69 'gradient-text'
                if props.get("background-clip") == "text" or props.get("-webkit-background-clip") == "text":
                    add("gradient-text", line, f"gradient-filled text in {sel}")
            # taste rules.mjs:71 'text-shadow'
            if prop == "text-shadow" and low != "none":
                add("text-shadow", line, f"text-shadow in {sel}")
            # taste rules.mjs:70 'shadow' (box-shadow at rest); DESIGN.md "Flat".
            # Zero-blur layers (focus rings, the status-pill inset ring) are not shadows.
            if prop == "box-shadow" and low != "none" and _has_blur(value):
                add("box-shadow", line, f"soft box-shadow in {sel}; separate with rules and paper-2")
            # taste rules.mjs:77 'glass' (backdrop blur)
            if prop in ("backdrop-filter", "-webkit-backdrop-filter") and "blur(" in low:
                add("glass", line, f"backdrop blur in {sel}")
            # taste rules.mjs:62 'micro-label' (small uppercase letter-spaced labels)
            if prop == "text-transform" and low == "uppercase" and _spaced(props):
                add("micro-label", line, f"uppercase letter-spaced label in {sel}; use sentence case")
            # DESIGN.md "keep one accent"; hallmark sloplint.mjs:125 parses !important.
            if "!important" in low and not reduced:
                add("important", line, f"!important on {prop} in {sel}")
            if prop == "font-family" or (prop.startswith("--font") and "," in value):
                key = ",".join(f.strip().strip("\"'").lower() for f in _split_top(value, ","))
                if not low.startswith("var("):
                    stacks.setdefault(key, line)
                for fam in _split_top(value, ","):
                    name = fam.strip().strip("\"'").lower()
                    if (name and not name.startswith("var(") and name not in GENERIC_FAMILIES
                            and name not in DESIGN_FAMILIES):
                        outside.setdefault(name, line)
            # hard-coded colours (DESIGN.md Colors; taste rules.mjs:8 colourFamily idea)
            if COLOUR_FN.search(value) or HEX.search(value):
                if prop.startswith("--"):
                    _token_colours(value, line, palette, prop, add)
                else:
                    _loose_colours(value, line, palette, prop, sel, add)
    # taste rules.mjs:101 'font-count' (more than 3 typefaces FAIL); DESIGN.md allows 2 stacks.
    if len(outside) > 2:
        add("font-count", min(outside.values()),
            "more than two font families outside the DESIGN.md stacks: " + ", ".join(sorted(outside)))
    if len(stacks) > 2:
        add("font-stacks", min(stacks.values()), f"{len(stacks)} different font stacks; DESIGN.md has sans and mono")
    out += _remote(text)
    out += _emoji(text)
    out += _status(text)
    return sorted(set(out), key=lambda f: (f[1], f[0], f[2]))


def _has_blur(value):
    """True when any box-shadow layer has a non-zero blur radius."""
    for layer in _split_top(value, ","):
        nums = re.findall(r"(?<![\w.#-])(-?\d*\.?\d+)(?:px|rem|em)?(?![\w%])",
                          re.sub(r"(?i)(rgba?|hsla?|oklch|oklab|color-mix)\([^)]*\)|#[0-9a-f]{3,8}\b", "", layer))
        if len(nums) >= 3 and float(nums[2]) != 0:
            return True
    return False


def _spaced(props):
    ls = props.get("letter-spacing", "0").strip().lower()
    return ls not in ("0", "0px", "0em", "normal", "") and not ls.startswith("-")


def _token_colours(value, line, palette, prop, add):
    # DESIGN.md: token blocks hold the DESIGN.md colours and nothing else.
    for h in HEX.findall(value):
        if palette and _norm_hex(h) not in palette:
            add("token-not-in-design", line, f"{prop}: {h} is not a DESIGN.md colour")
    if COLOUR_FN.search(value) and palette:
        add("token-not-in-design", line, f"{prop}: {value[:40]} is not a DESIGN.md hex value")


def _loose_colours(value, line, palette, prop, sel, add):
    # taste rules.mjs:85-93 palette checks; pure black and white are not used by the drawn palette; DESIGN.md Colors.
    for h in HEX.findall(value):
        n = _norm_hex(h)
        if n in ("#000000", "#ffffff"):
            add("pure-black-white", line, f"{prop}: {h} in {sel}; use ink or paper")
        elif n not in palette:
            add("hardcoded-colour", line, f"{prop}: {h} in {sel} is not a DESIGN.md value; use a token")
    if COLOUR_FN.search(value):
        add("hardcoded-colour", line, f"{prop}: colour function in {sel}; use a var(--token)")
    if re.search(r"(?<![\w-])(?:black|white)(?![\w-])", value, re.I) and prop in (
            "color", "background", "background-color", "border-color", "border"):
        add("pure-black-white", line, f"{prop}: keyword black/white in {sel}")


def _remote(text):
    """Remote assets and web fonts. DESIGN.md "Don't load web fonts or remote assets"."""
    out = []
    for m in re.finditer(r"(?i)fonts\.(?:googleapis|gstatic)\.com", text):
        out.append(("remote-asset", _line(text, m.start()), "Google Fonts host"))
    for m in re.finditer(r"(?i)@import\s+(?:url\(\s*)?[\"']?(?:https?:)?//[^\s\"')]+", text):
        out.append(("remote-asset", _line(text, m.start()), "remote @import"))
    for m in re.finditer(r"(?i)url\(\s*[\"']?((?:https?:)?//[^\s\"')]+)", text):
        out.append(("remote-asset", _line(text, m.start()), f"remote url() {m.group(1)[:60]}"))
    for m in re.finditer(r"(?is)<(script|img|source|iframe|video|audio|link|embed|object)\b([^>]*)>", text):
        attrs = m.group(2)
        a = re.search(r"""(?i)\b(src|href|data)\s*=\s*["']?((?:https?:)?//[^\s"'>]+)""", attrs)
        if a and (m.group(1).lower() != "link" or re.search(r"(?i)rel=[\"']?(stylesheet|preload|icon|preconnect)", attrs)):
            out.append(("remote-asset", _line(text, m.start()), f"remote {a.group(1)} {a.group(2)[:60]}"))
    return out


def _emoji(text):
    """Emoji and dingbats used as icons or markers. taste rules.mjs:64 'emoji' (FAIL); DESIGN.md."""
    out = []
    for no, raw in enumerate(text.split("\n"), 1):
        found = EMOJI.findall(_html.unescape(raw))
        if found:
            out.append(("emoji", no, "emoji or dingbat " + " ".join(sorted(set(found))) + "; use a word"))
    return out


def _status(text):
    """A status element must hold a word. DESIGN.md "Do show every state as a word"."""
    out = []
    for m in re.finditer(r"(?is)<([a-z][a-z0-9]*)\b([^>]*)>", text):
        tag, attrs = m.groups()
        if tag in ("script", "style", "svg", "html", "head", "body"):
            continue
        close = re.search(r"(?is)</%s\s*>" % tag, text[m.end():])
        inner = text[m.end():m.end() + close.start()] if close else ""
        cls = re.search(r"""(?i)\bclass\s*=\s*["']([^"']*)["']""", attrs)
        if not cls or not any(STATUS_CLASS.search(c) for c in cls.group(1).split()):
            continue
        if re.search(r"(?i)\b(aria-label|title)\s*=\s*[\"'][^\"']*\w", attrs):
            continue
        words = re.sub(r"(?s)<[^>]*>", "", inner)
        if not re.search(r"[A-Za-z]{2,}", _html.unescape(words)):
            out.append(("status-no-word", _line(text, m.start()),
                        f'<{tag} class="{cls.group(1)}"> has no status word'))
    return out


def main(argv):
    if not argv:
        print("usage: python3 tests/slop_lint.py <file.html> [...]", file=sys.stderr)
        return 2
    found = 0
    for path in argv:
        with open(path, encoding="utf-8") as handle:
            for rule, line, msg in lint(handle.read()):
                print(f"{path}:{line}: {rule}: {msg}")
                found += 1
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# Rules read but not ported.
# not ported: needs browser  taste rules.mjs headline-lines, statement-length, focal-point, hero-words, mixed-font-headline (text wrap and size)
# not ported: needs browser  taste rules.mjs eyebrow, numbering (need heading and DOM geometry)
# not ported: needs browser  taste rules.mjs hairline, outlined-box, dashed, icon-cards, card-rows, pill-nav (computed box styles)
# not ported: needs browser  taste rules.mjs contrast, grey-body, default-link (computed foreground and ground)
# not ported: needs browser  taste rules.mjs font-fallback, size-count, body-size, measure, small-text, all-centred (computed type)
# not ported: needs browser  taste rules.mjs few-pictures, no-real-pictures, no-footage, no-poster, broken-image (rendered media)
# not ported: needs browser  taste rules.mjs off-centre, lopsided, empty-middle, blank-gap, edge-text, ragged-edges, overflow, side-scroll (layout)
# not ported: needs browser  taste rules.mjs no-title, many-h1, untitled-section, first-action, no-hero, hero-void (first screen)
# not ported: needs browser  taste rules.mjs judgeApp rules sidebar-phone, unused-canvas, heavy-shadow, heavy-borders, radius-mix, icon-chips, numeric-align, tabular, rainbow-chart, colour-sprawl, placeholder-data, tiny-text, ragged-row, below-fold, panel-void, app-title-size, kpi-size, icon-tiles
# not ported: needs browser  hallmark sloplint-render.mjs gradient contrast (line 609), empty gradient (873), blend-text, dwell and motion probes
# not ported: does not fit   taste rules.mjs mono (DESIGN.md sets paths, hashes and run labels in mono)
# not ported: does not fit   taste rules.mjs palette-claude, palette-terracotta, palette-cream, palette-purple (DESIGN.md fixes the palette; token-not-in-design covers it)
# not ported: does not fit   taste rules.mjs hairline and outlined-box as static rules (DESIGN.md uses rule lines on purpose)
# not ported: does not fit   hallmark sloplint.mjs icon-library detection (sloplint-render.mjs:1720; pages draw no icons)
# not ported: does not fit   hallmark sloplint.mjs hover lift (3259), Tailwind palette and shadow classes (3318, 3522); pages use plain CSS
