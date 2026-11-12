"""Check an Artifact evaluation page before it is published. Read-only.

Run from stdin so the gate reads no script path, with every option as --flag=value:
    sh <plugin>/hooks/py.sh - --page=<page.html> --report=<reports/name.qmd> [--numbers=<numbers.json>]
        [--hooks=<plugin>/hooks] < artifact_check.py
Without --numbers, and with --hooks, the numbers file is the one `analysis_paths.numbers()` resolves for the
analysis folder (the parent of reports/) and its current run.

Checks the page contract (no doctype/html/head/body, a <title> in the first 8 KB, the viewport meta, the
dark-mode token blocks, a body background, no colour literal outside the token blocks, script and
stylesheet hosts, no alert/confirm/print/download, at most 16 MB), the banner, and that every number on
the page appears in the .qmd or in numbers.json. Numbers inside <code class="hash">, inside data URIs, in
<style>/<script>, in ISO dates (YYYY-MM-DD), and glued to letters or underscores (s01, run_2, 12px) are not claims and are skipped.
Exit 0 when clean, 1 with one finding per line. Stdlib-only; Python 3.9+.
"""

import argparse
import html
import json
import os
import re
import sys
from urllib.parse import urlparse

MAX_BYTES = 16 * 1024 * 1024
SCRIPT_HOSTS = {"cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "cdn.tailwindcss.com", "code.jquery.com"}
STYLE_HOSTS = {"fonts.googleapis.com"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?!\w|\.[A-Za-z])")
DATA_URI = re.compile(r"data:[a-zA-Z0-9.+/-]+;base64,[A-Za-z0-9+/=\s]*")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


THOUSANDS = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")


def split_lists(tokens):
    """A token like `1,2,3` is a list of numbers; `14,231` (thousands) and `1,5` stay whole only when they
    match the thousands pattern, so the others split at the commas."""
    out = []
    for token in tokens:
        out += [token] if "," not in token or THOUSANDS.fullmatch(token) else [t for t in token.split(",") if t]
    return out


def numbers_in(text):
    """Number tokens as written, plus a form without thousands commas and trailing zeros."""
    found = set()
    for token in split_lists(NUMBER.findall(text)):
        found.add(token)
        plain = token.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", token) else token
        found.add(plain)
        if "." in plain:
            found.add(plain.rstrip("0").rstrip("."))
    return found


def json_text(node):
    """Every scalar of the JSON as text, so 0.003 and 1e-3 style values both reach the number scan."""
    if isinstance(node, dict):
        return " ".join(json_text(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(json_text(v) for v in node)
    if isinstance(node, float):
        return " ".join({repr(node), "{:g}".format(node), "{:.10f}".format(node).rstrip("0").rstrip(".")})
    return str(node)


def page_text(page):
    """The reader-visible text: no data URIs, style, script, hash codes or tags."""
    text = DATA_URI.sub(" ", page)
    text = re.sub(r"<(style|script)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r'<code class="hash">.*?</code>', " ", text, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " ", html.unescape(text))  # a date (the banner's last change) is not a claim


def contract(page, size):
    out = []
    if size > MAX_BYTES:
        out.append("size: {:.1f} MB is over the 16 MB limit".format(size / 1048576))
    tag = re.search(r"<(!doctype|html|head|body)\b", page, re.I)
    if tag:
        out.append("contract: the page has its own <{}> (the host supplies the skeleton)".format(tag.group(1)))
    title = re.search(r"<title>(.*?)</title>", page[:8192], re.S | re.I)
    if not title:
        out.append("contract: no <title> in the first 8 KB")
    elif not title.group(1).strip():
        out.append("contract: <title> is empty")
    if not re.search(r'<meta\s+name="claude:viewport-fit-sides"\s+content="cover"', page):
        out.append('contract: missing <meta name="claude:viewport-fit-sides" content="cover">')
    if not re.search(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root:not\(\[data-theme=[\"']light[\"']\]\)", page):
        out.append("contract: no dark-mode token block under @media (prefers-color-scheme: dark) { :root:not([data-theme=\"light\"]) }")
    if not re.search(r":root\[data-theme=[\"']dark[\"']\]\s*\{", page):
        out.append('contract: no :root[data-theme="dark"] token block')
    if len(re.findall(r"color-scheme:\s*dark", page)) < 2:
        out.append("contract: color-scheme: dark must appear in both dark blocks")
    if not re.search(r"(^|[}\s,])body\s*\{[^}]*background\s*:\s*var\(--", page):
        out.append("contract: body has no token background")
    css = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", page, re.S | re.I))
    loose = re.sub(r"[^{}]*:root[^{]*\{[^}]*\}", " ", css)  # token blocks, plain and inside @media
    for literal in sorted(set(re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)", loose))):
        out.append("contract: colour literal {} outside the :root token blocks".format(literal))
    for tagtext in re.findall(r"<script\b[^>]*>", page, re.I):
        src = re.search(r'src\s*=\s*["\']([^"\']+)', tagtext)
        host = urlparse(src.group(1)).hostname if src else None
        if src and host not in SCRIPT_HOSTS:
            out.append("contract: script host not allowed: {}".format(src.group(1)))
        elif src and not re.search(r"[@/]\d+\.\d+\.\d+", src.group(1)):  # `pkg@1.2.3` or cdnjs `/pkg/1.2.3/`
            out.append("contract: script not pinned to an exact version: {}".format(src.group(1)))
    for tagtext in re.findall(r"<link\b[^>]*>", page, re.I):
        href = re.search(r'href\s*=\s*["\']([^"\']+)', tagtext)
        if href and "stylesheet" in tagtext and urlparse(href.group(1)).hostname not in STYLE_HOSTS:
            out.append("contract: stylesheet host not allowed: {}".format(href.group(1)))
    for pattern, what in ((r"\balert\s*\(", "alert()"), (r"\bconfirm\s*\(", "confirm()"), (r"window\.print", "a print call"),
                          (r"<a\b[^>]*\bdownload\b", "a download link")):
        if re.search(pattern, DATA_URI.sub(" ", page)):
            out.append("contract: the page uses {}".format(what))
    return out


def banner(page):
    out = []
    block = re.search(r"<(\w+)\b[^>]*\bdata-banner\b[^>]*>(.*?)</\1>", page, re.S)
    if not block:
        return ["banner: no element with data-banner"]
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", block.group(2))))
    if "Evaluation copy. The record is reports/" not in text:
        out.append('banner: missing "Evaluation copy. The record is reports/<name>.html"')
    if not re.search(r"\bnot verified\b|\bverified\b", text):
        out.append("banner: no verified / not verified word")
    if not re.search(r"\.qmd", text):
        out.append("banner: does not name the .qmd")
    if len(re.findall(r'<code class="hash">\s*[0-9a-f]{4,}\s*</code>', block.group(2))) < 2:
        out.append("banner: needs the plan hash and the .qmd short hash, each in <code class=\"hash\">")
    if not re.search(r"\brun\b|outputs/ \(steps\)", text, re.I):  # a steps layout has no run label
        out.append("banner: does not name the run label or outputs/ (steps)")
    return out


def invented(page, report, numbers):
    known = numbers_in(report) | numbers_in(numbers)
    seen, out = set(), []
    for token in split_lists(NUMBER.findall(page_text(page))):
        variants = numbers_in(token)
        if token not in seen and not variants & known:
            out.append("number: {} is in neither the .qmd nor numbers.json".format(token))
        seen.add(token)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--numbers")
    parser.add_argument("--hooks", help="the plugin's hooks/ folder; lets the default numbers file come from the resolver")
    args = parser.parse_args()
    page = read(args.page)
    size = os.path.getsize(args.page)
    numbers = ""
    if not args.numbers and args.hooks:  # resolver default: <run>/numbers.json, else outputs/numbers.json
        sys.path.insert(0, args.hooks)
        import analysis_paths
        folder = os.path.dirname(os.path.dirname(os.path.abspath(args.report)))
        args.numbers = analysis_paths.numbers(folder, analysis_paths.current_run(folder)[0])
    if args.numbers and os.path.isfile(args.numbers):  # not every analysis registers values; a missing file is not a finding
        numbers = json_text(json.loads(read(args.numbers)))
    findings = contract(page, size) + banner(page) + invented(page, read(args.report), numbers)
    for line in findings:
        print(line)
    if findings:
        print("artifact_check: {} finding(s); do not publish".format(len(findings)))
        return 1
    print("artifact_check: clean ({:.2f} MB)".format(size / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
