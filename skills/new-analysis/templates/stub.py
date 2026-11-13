"""@@FILE@@: step @@NUM@@ of @@NAME@@.

Purpose: [One sentence: what this step answers or prepares.]
Run:     python @@PATH@@ @@USAGE@@   (the Snakefile passes these paths)
Inputs:  @@INPUT@@ [producer or [gap]]
Outputs: @@OUTPUT@@ [what the table holds]

Register numbers a report would quote with Mycelium's register_value
(skills/core/references/report-values-guide.md); it writes outputs/numbers.json.
"""

import sys
from importlib.metadata import packages_distributions, version
from pathlib import Path

# Parameters -------------------------------------------------------------------
# Values a reader may change, UPPER_SNAKE, with the reason beside each. Delete the block if there are none.
SEED = 0  # pass to every RNG, e.g. np.random.default_rng(SEED)

# Arguments --------------------------------------------------------------------
@@ARGS_CODE@@
step_dir = Path(output_path).parent  # this step's folder, outputs/@@STEM@@

# Load data --------------------------------------------------------------------
# Name one check where tables meet, e.g.
# if list(meta["id"]) != list(counts.columns):
#     raise ValueError("meta rows do not match counts")
raise SystemExit("@@FILE@@ is not written yet")

# Session info -----------------------------------------------------------------
# A script that uses scanpy writes sc.logging.print_versions() here instead.
(step_dir / "logs").mkdir(exist_ok=True)
# Every package imported above, found from sys.modules, so no list to keep by hand.
owners = packages_distributions()
packages = sorted({d for m in {n.split(".")[0] for n in sys.modules} for d in owners.get(m, [])})
notes = [f"python {sys.version.split()[0]}"] + [f"{name} {version(name)}" for name in packages]
(step_dir / "logs" / "@@STEM@@.session.txt").write_text("\n".join(notes) + "\n")
