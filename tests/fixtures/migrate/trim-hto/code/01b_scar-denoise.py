"""01b_scar-denoise.py: step 01b of trim-hto.
Run:     python code/01b_scar-denoise.py <batch> <valid_tags.tsv> <out_dir>
"""
import sys
from pathlib import Path

batch, valid_tags_path, out_root = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
out_dir = out_root / batch
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "run_info.json").write_text("{}")
(out_dir / "ambient_grid.tsv").write_text("a\tb\n")
