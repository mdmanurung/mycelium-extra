"""Run: python3 tests/test_slop_lint.py

Unit tests for tests/slop_lint.py (one failing and one passing page per rule) and a lint of the
real generated pages in docs/examples/.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import slop_lint  # noqa: E402

REPO = os.path.dirname(HERE)
EXAMPLES = ["analysis-journal.html", "track-changes-report.html", "analysis-journal-missing.html"]


def page(css="", body=""):
    return f"<!doctype html><html><head><style>\n{css}\n</style></head><body>{body}</body></html>"


def ids(html):
    return {rule for rule, _, _ in slop_lint.lint(html)}


# rule id -> (page that must trigger it, page that must not)
CASES = {
    "gradient": (
        page("body { background: linear-gradient(#fff, #eee); }"),
        page("body { background: #f9fbfd; }")),
    "gradient-text": (
        page(".h { background: linear-gradient(red, blue); background-clip: text; }"),
        page(".h { color: #111921; }")),
    "text-shadow": (
        page(".h { text-shadow: 0 1px 2px #111921; }"),
        page(".h { text-shadow: none; }")),
    "box-shadow": (
        page(".card { box-shadow: 0 8px 24px #111921; }"),
        page(".pill { box-shadow: inset 0 0 0 1px #277a55; }")),
    "glass": (
        page(".bar { backdrop-filter: blur(8px); }"),
        page(".bar { background: #f9fbfd; }")),
    "micro-label": (
        page(".k { text-transform: uppercase; letter-spacing: 0.12em; }"),
        page(".k { text-transform: uppercase; }")),
    "important": (
        page(".a { color: #111921 !important; }"),
        page("@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }")),
    "font-face": (
        page("@font-face { font-family: Inter; src: url(data:font/woff2;base64,AAAA); }"),
        page("body { font-family: system-ui, sans-serif; }")),
    "font-count": (
        page("a { font-family: Inter, sans-serif; } b { font-family: Lora, serif; } "
             "i { font-family: Fira Code, monospace; }"),
        page("a { font-family: ui-sans-serif, 'Segoe UI', Roboto, sans-serif; }")),
    "font-stacks": (
        page("a { font-family: system-ui; } b { font-family: ui-monospace; } "
             "i { font-family: serif; }"),
        page("a { font-family: system-ui; } b { font-family: ui-monospace; }")),
    "remote-asset": (
        page("", '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'),
        page("", '<a href="https://example.org/">docs</a>')),
    "emoji": (
        page("", "<p>✅ passed</p>"),
        page("", "<p>pass</p>")),
    "pure-black-white": (
        page("body { color: #000; background: #ffffff; }"),
        page("body { color: #111921; background: #f9fbfd; }")),
    "hardcoded-colour": (
        page(".a { color: #123456; }"),
        page(".a { color: var(--ink); } .b { color: #00696f; }")),
    "token-not-in-design": (
        page(":root { --ink: oklch(22% 0.01 90); }"),
        page(":root { --ink: #111921; --accent: #00696f; }")),
    "status-no-word": (
        page("", '<span class="pill pass"></span>'),
        page("", '<span class="pill pass">pass</span><span class="dot" aria-label="gap"></span>')),
}


class RuleCases(unittest.TestCase):
    def test_every_rule_has_a_case(self):
        self.assertEqual(set(CASES), set(slop_lint.RULES))

    def test_bad_pages_fail_and_good_pages_pass(self):
        for rule, (bad, good) in CASES.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, ids(bad), "bad page should trigger the rule")
                self.assertNotIn(rule, ids(good), "good page should not trigger the rule")

    def test_json_data_script_is_not_linted(self):
        html = page("", '<script type="application/json" id="data">{"t": "✅ #123456"}</script>')
        self.assertEqual(slop_lint.lint(html), [])

    def test_line_numbers_point_at_the_declaration(self):
        findings = slop_lint.lint("<style>\na { color: #fff; }\nb { background: linear-gradient(red, blue); }\n</style>")
        self.assertIn(("gradient", 3), {(r, n) for r, n, _ in findings})

    def test_cli_exit_code(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.html")
            good = os.path.join(tmp, "good.html")
            with open(bad, "w", encoding="utf-8") as h:
                h.write(CASES["gradient"][0])
            with open(good, "w", encoding="utf-8") as h:
                h.write(CASES["gradient"][1])
            run = lambda p: subprocess.run([sys.executable, "-I", os.path.join(HERE, "slop_lint.py"), p],
                                           capture_output=True, text=True)
            self.assertEqual(run(bad).returncode, 1)
            self.assertEqual(run(good).returncode, 0)


class RealPages(unittest.TestCase):
    def findings(self, name):
        with open(os.path.join(REPO, "docs", "examples", name), encoding="utf-8") as handle:
            return slop_lint.lint(handle.read())

    def test_pages_break_no_rule(self):
        for name in EXAMPLES:
            with self.subTest(page=name):
                self.assertEqual(self.findings(name), [])


if __name__ == "__main__":
    unittest.main()
