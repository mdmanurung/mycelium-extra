"""@@FILE@@: step @@NUM@@ of @@NAME@@.

Input:  @@INPUT@@
Output: @@OUTPUT@@
Run:    python @@FILE@@ @@USAGE@@   (the Snakefile passes these paths)

Register numbers a report would quote with Mycelium's register_value
(skills/core/references/report-values-guide.md); it writes outputs/numbers.json.
"""

import sys

SEED = 0  # pass to every RNG, e.g. np.random.default_rng(SEED)
@@ARGS_CODE@@

# Fail loudly on unexpected data: check shapes and counts, never drop rows silently.

raise SystemExit("@@FILE@@ is not written yet")
