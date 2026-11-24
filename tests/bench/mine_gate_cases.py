#!/usr/bin/env python3
"""Mine command strings from the hook tests into a regression corpus.

Run: python3 tests/bench/mine_gate_cases.py   (writes tests/bench/gate_corpus/mined.jsonl)

Every one-line string constant in the test files below that starts like a shell
command becomes a case. Its `expect` is what the classifier returns today in the
bench layout, so these cases score zero at the commit they were mined from. They
catch a change that alters a decision the suite already relies on; they do not
show today's mistakes (the hand-labelled seeds do that). Rerun only on purpose:
remining after a fix ratifies the fix's output as the new label.
"""

import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import score_gate  # noqa: E402

SOURCES = ("hooks/tests/test_gate*.py", "hooks/tests/test_shellwords.py", "hooks/tests/test_loop_guard*.py")
COMMAND_START = re.compile(
    r"^\s*(\(|[A-Z_]+=\S+ )?\s*(python3?|Rscript|R |bash|sh |zsh|sbatch|snakemake|nextflow|cd |srun|env |nohup"
    r"|time |quarto|jupyter|uv |pixi|conda|mamba|micromamba|cat |echo |exec |command |xargs|find |make|git "
    r"|for |while |source|\. |pushd|nice|timeout|setsid|stdbuf|ionice|julia|perl|node)"
)


def main():
    commands = {}
    for pattern in SOURCES:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                text = node.value if isinstance(node, ast.Constant) else None
                if isinstance(text, str) and "\n" not in text and len(text) < 300 and COMMAND_START.match(text):
                    commands.setdefault(text, os.path.relpath(path, ROOT))

    gate = score_gate.load_gate(os.path.join(ROOT, "hooks"))
    config = dict(gate.DEFAULTS, _notices=[])
    root = score_gate.build_layout()
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    out = os.path.join(HERE, "gate_corpus", "mined.jsonl")
    try:
        with open(out, "w", encoding="utf-8") as handle:
            for number, (command, source) in enumerate(sorted(commands.items()), 1):
                try:
                    expect = sorted(score_gate.targets(gate, command, root, root, config))
                except Exception:  # a command the classifier cannot read is not a regression anchor
                    continue
                handle.write(json.dumps({
                    "id": "m{:04d}".format(number),
                    "family": "mined",
                    "command": command,
                    "cwd": ".",
                    "expect": expect,
                    "label": "current output at {}".format(head),
                    "source": source,
                }) + "\n")
    finally:
        shutil.rmtree(root)
    print(out)


if __name__ == "__main__":
    main()
