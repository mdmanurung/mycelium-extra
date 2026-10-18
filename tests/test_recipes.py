"""The validation-bindings blocks in docs/validation-recipes.md parse with the gate's own reader."""

import json
import os
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hooks"))
import validation  # noqa: E402

PAGE = os.path.join(HERE, "..", "docs", "validation-recipes.md")
BLOCK = re.compile(r"<!--\s*validation-bindings\b.*?-->", re.DOTALL)


class Recipes(unittest.TestCase):
    def test_every_binding_in_the_page_is_valid(self):
        with open(PAGE, encoding="utf-8") as handle:
            blocks = BLOCK.findall(handle.read())
        self.assertEqual(len(blocks), 3, "one binding block per recipe")
        for text in blocks:
            checks = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))["checks"]
            with tempfile.TemporaryDirectory() as root:
                for check in checks:
                    for rel in check["test_paths"]:
                        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                        with open(os.path.join(root, rel), "w") as handle:
                            handle.write("x\n")
                rows = sorted({c["plan_row"] for c in checks})
                found, errors = validation.read_bindings(text, rows, root)
                self.assertEqual(errors, [], text)
                self.assertEqual(len(found["checks"]), len(checks))


if __name__ == "__main__":
    unittest.main()
