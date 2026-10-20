# Real Snakemake `--use-conda` env folder (trimmed)

What `snakemake --use-conda --conda-frontend conda` built on 2026-10-20 (Snakemake 9.27.0, conda 24.9.2, linux-64, Python 3.11.17) for one rule whose `conda:` file is `tiny.yaml` below. Copy `snakemake-dir/` to `<workdir>/.snakemake/` to use it. Nothing here was written by hand except the trimming.

- Layout (the part `verify` depends on): `conda/<hash>_.yaml` (a byte copy of the rule's env file), `conda/<hash>_/` (the env, note the trailing underscore), `conda/<hash>_.env_setup_done`.
- `conda-meta/*.json` keeps `name`, `version`, `url`, `md5`, `sha256`, `build`, `channel`, `fn`, `size`, `subdir` and only the `site-packages` entries of `files`. The rest (absolute local paths, `paths_data`) is dropped.
- `lib/python3.11/site-packages` keeps each `*.dist-info` with `METADATA` (headers only), `INSTALLER` and `REQUESTED`; no package code.
- `lib/python3.1` is a symlink to `python3.11`, as conda-forge's Python ships it; it makes a `lib/python*` glob list every package twice.
- `six==1.16.0` came from the env file's `pip:` section; the other 26 packages are conda records.
- `tiny.yaml` (the rule's env file, byte-identical to the `<hash>_.yaml` copy):

```yaml
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      - six==1.16.0
```
