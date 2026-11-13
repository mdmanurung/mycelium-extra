"""Run: python3 skills/new-analysis/tests/test_migrate.py

Tests new_analysis.py --migrate on tests/fixtures/migrate/trim-hto, a trimmed copy of the structure of a real
run-folder analysis. The snakemake test needs a real Snakemake: MX_SNAKEMAKE, the HPC path, or snakemake on PATH.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..")
SCRIPT = os.path.join(SKILL, "scripts", "new_analysis.py")
TEMPLATES = os.path.join(SKILL, "templates")
FIXTURE = os.path.join(HERE, "..", "..", "..", "tests", "fixtures", "migrate", "trim-hto")
HPC_SNAKEMAKE = "/exports/archive/hg-funcgenom-research/mdmanurung/conda/envs/snakemake/bin/snakemake"
sys.path.insert(0, os.path.join(SKILL, "..", "..", "hooks"))
import analysis_paths as ap  # noqa: E402

BASELINE, GATECHECK = "run_20261111_baseline", "run_20261112_gatecheck"


def snakemake_path():
    found = os.environ.get("MX_SNAKEMAKE") or (HPC_SNAKEMAKE if os.path.isfile(HPC_SNAKEMAKE) else shutil.which("snakemake"))
    return found


def run(cwd, *args):
    with open(SCRIPT) as source:
        return subprocess.run([sys.executable, "-", "--templates=" + TEMPLATES] + list(args),
                              stdin=source, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def snapshot(folder):
    """{relative path: sha256 or link target} for every file and link below folder."""
    state = {}
    for here, dirs, files in os.walk(folder):
        for name in dirs + files:
            path = os.path.join(here, name)
            rel = os.path.relpath(path, folder)
            if os.path.islink(path):
                state[rel] = "->" + os.readlink(path)
            elif os.path.isdir(path):
                state[rel] = "dir"
            else:
                with open(path, "rb") as handle:
                    state[rel] = hashlib.sha256(handle.read()).hexdigest()
    return state


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        os.mkdir(os.path.join(self.root, ".living"))
        self.dest = os.path.join(self.root, "analysis", "trim-hto")
        shutil.copytree(FIXTURE, self.dest, symlinks=True)
        shutil.copy(os.path.join(self.dest, "gitignore.txt"), os.path.join(self.dest, ".gitignore"))
        self.before = snapshot(self.dest)

    def tearDown(self):
        shutil.rmtree(self.root)

    def migrate(self, *args, code=0):
        proc = run(self.root, "--dest=analysis/trim-hto", "--migrate", *args)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout

    def refused(self, *args, fragment):
        out = self.migrate(*args, code=1)
        self.assertIn("refused", out)
        self.assertIn(fragment, out)
        return out

    def path(self, *parts):
        return os.path.join(self.dest, *parts)

    def new_snakefile(self):
        return read(self.path("Snakefile.new"))

    # ---------------------------------------------------------------- default mode

    def test_default_writes_only_new_files_and_prints_the_diff(self):
        out = self.migrate()
        after = snapshot(self.dest)
        added = set(after) - set(self.before)
        self.assertEqual(added, {"Snakefile.new", "run.sh.new", "run.sbatch.new", "_quarto.yml.new", "MIGRATE.md"})
        self.assertEqual({k: v for k, v in after.items() if k in self.before}, self.before)  # no original changed
        self.assertIn("--- Snakefile\n+++ Snakefile.new", out)
        self.assertIn('-        f"{OUT}/01_valid-tags.rds",', out)
        self.assertIn('+        "outputs/01_valid-tags/01_valid-tags.rds",', out)
        self.assertIn("7 of 7 rules rewritten", out)
        self.assertTrue(os.access(self.path("run.sh.new"), os.X_OK))

    def test_rewrite_rules(self):
        self.migrate()
        text = self.new_snakefile()
        for gone in ("RUN =", "BASE =", "OUT =", "_BASE_RUN", "{OUT", "{BASE", "RUN_DIR", "import os", 'config.get("run")'):
            self.assertNotIn(gone, text, gone)
        # the block goes; interpreters, wildcard constraints, resources and threads stay
        self.assertIn('RSCRIPT = config.get("rscript", "Rscript")', text)
        self.assertIn('        batch="B1a|B1b",', text)
        self.assertIn('        slurm_partition="gpu",\n        gres="gpu:1",', text)
        self.assertIn("    threads: 8", text)
        # own outputs, logs and benchmarks go under outputs/<stem>/; the f prefix and doubled braces go with the block
        self.assertIn('        "outputs/01_valid-tags/tables/01_valid_tags.tsv",', text)
        self.assertIn('        "outputs/01_valid-tags/logs/01_valid-tags.log",', text)
        self.assertIn('        "outputs/01_valid-tags/logs/01_valid-tags.benchmark.tsv"', text)
        # a folder that differs from the script stem (01b_scar) becomes the step folder
        self.assertIn('        info="outputs/01b_scar-denoise/{batch}/run_info.json",', text)
        self.assertIn('        "outputs/01b_scar-denoise/logs/01b_scar-denoise_{batch}.log",', text)
        self.assertIn("{input.tags:q} outputs/01b_scar-denoise > {log:q} 2>&1", text)
        # reads of other steps, from OUT and from BASE, map to the producing step by number
        self.assertIn('        prev="outputs/01_valid-tags/01_valid-tags.rds",', text)
        self.assertIn('        scar=expand("outputs/01b_scar-denoise/{batch}/run_info.json", batch=BATCHES),', text)
        self.assertIn('        base="outputs/01_valid-tags/01_valid-tags.rds",', text)
        self.assertIn('        base="outputs/01_valid-tags/tables/01_valid_tags.tsv",', text)
        self.assertIn('        arms="outputs/06_tag-dominance/tables/06_tag_dominance.tsv",', text)
        # the all rule: an expand with a wildcard and a page
        self.assertIn('            "outputs/13_timepoint-figures/figures/13_{stem}.png",', text)
        self.assertIn('        "outputs/13_timepoint-figures/13_timepoint-figures.html",', text)
        self.assertNotIn('"reports/site', text)
        # a qmd step: the scaffold's render command, RUN_DIR becomes STEP_DIR and OUTPUTS
        self.assertIn('THREADS + "QUARTO_R={RSCRIPT:q} STEP_DIR=outputs/13_timepoint-figures OUTPUTS=outputs {QUARTO:q} render '
                      '{input.script:q} --output-dir outputs/13_timepoint-figures > {log:q} 2>&1 && '
                      'mv outputs/13_timepoint-figures/code/13_timepoint-figures.html '
                      'outputs/13_timepoint-figures/13_timepoint-figures.html && rmdir outputs/13_timepoint-figures/code"', text)
        self.assertIn("BASE_DIR=outputs STEP_DIR=outputs/10_gate-figures OUTPUTS=outputs {QUARTO:q}", text)
        # the same command the current scaffold writes for a qmd step
        with open(SCRIPT) as source:
            scaffold = source.read()
        self.assertIn('"{{QUARTO:q}} render {{input.script:q}} --output-dir {0} > {{log:q}} 2>&1 && "', scaffold)
        self.assertIn('"mv {0}/code/{1}.html {2} && rmdir {0}/code"', scaffold)
        # the header comes from the current template
        self.assertTrue(text.startswith('"""trim-hto: run the numbered steps in order.'))
        self.assertIn("bash run.sh   (runs this file", text)

    def test_other_new_files_come_from_the_templates(self):
        self.migrate()
        self.assertEqual(read(self.path("run.sh.new")), read(os.path.join(TEMPLATES, "run.sh")).replace("@@NAME@@", "trim-hto"))
        self.assertEqual(read(self.path("run.sbatch.new")),
                         read(os.path.join(TEMPLATES, "run.sbatch")).replace("@@NAME@@", "trim-hto"))
        self.assertEqual(read(self.path("_quarto.yml.new")), read(os.path.join(TEMPLATES, "_quarto.yml")))

    def test_no_quarto_file_without_qmd(self):
        os.unlink(self.path("_quarto.yml"))
        for name in ("10_gate-figures.qmd", "13_timepoint-figures.qmd"):
            os.unlink(self.path("code", name))
        self.migrate()
        self.assertFalse(os.path.exists(self.path("_quarto.yml.new")))

    def test_unmapped_path_keeps_a_comment_and_is_listed(self):
        self.migrate()
        text = self.new_snakefile()
        lines = [l for l in text.split("\n") if "# MIGRATE: check" in l]
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(any('notes="outputs/notes/readme.txt"' in l for l in lines))
        self.assertTrue(any("{RSCRIPT:q} {input.script:q} outputs {output[0]:q}" in l for l in lines))  # the bare BASE argument
        self.assertTrue(any("BASE_DIR=outputs" in l for l in lines))
        report = read(self.path("MIGRATE.md"))
        number = text.split("\n").index(next(l for l in lines if "readme.txt" in l)) + 1
        self.assertIn("`Snakefile.new:{}` `notes=\"outputs/notes/readme.txt\",`".format(number), report)
        self.assertIn("## Paths to check", report)

    def test_report_lists_rules_code_reads_gitignore_and_warnings(self):
        out = self.migrate()
        report = read(self.path("MIGRATE.md"))
        self.assertIn("7 of 7 rules changed", report)
        self.assertIn("| `step01b_scar_denoise` | `outputs/01b_scar-denoise/` |", report)
        self.assertIn("`01b_scar` to `01b_scar-denoise`", report)
        # a file:line checklist of cross-step reads in code/
        for item in ("`code/02_restricted-calls.R:6` `run_dir <- dirname(input_path)`",
                     "`code/02_restricted-calls.R:7`", "`code/06_tag-dominance.R:5` `base_dir <- args[[1]]`",
                     "`code/06_tag-dominance.R:9`", "`code/10_gate-figures.qmd:8`", "(run_dir)",
                     "`code/13_timepoint-figures.qmd:6`", "`code/10_gate-figures.qmd:9`"):
            self.assertIn(item, report)
        self.assertIn("- [ ] `code/06_tag-dominance.R:9`", report)
        self.assertIn("`code/02_restricted-calls.R:10` `grid <- read.delim(\"outputs/latest/01b_scar/B1a/ambient_grid.tsv\")` (01b_scar/)", report)  # a results folder that differs from the script stem
        self.assertNotIn("`code/01b_scar-denoise.py:", report)  # the script stem alone is no read
        self.assertNotIn("code/theme.R", report)
        # .gitignore: suggestions only
        self.assertIn("`/outputs/**/01b_scar/` names the old folder `01b_scar`", report)
        self.assertIn("add `/outputs/01b_scar-denoise/`", report)
        self.assertIn("git ignores `logs/CHANGES.md`", report)
        self.assertEqual(read(self.path(".gitignore")), read(self.path("gitignore.txt")))
        self.assertIn("note: .gitignore:", out)
        # the mixed layout and the first run
        self.assertIn("## Mixed layout", report)
        self.assertIn("resolver lists the step folders first and the run folders after", report)
        self.assertIn("keeps working, because it uses that path directly", report)
        self.assertIn("`logs/.code-hashes.tsv` is absent, so the first `run.sh` entry lists every file in `code/` as new.", report)
        self.assertIn("not `reports/site`", report)

    def test_code_is_never_edited(self):
        self.migrate("--apply")
        after = snapshot(self.dest)
        for rel, digest in self.before.items():
            if rel.startswith("code") or rel.startswith("outputs"):
                self.assertEqual(after.get(rel), digest, rel)

    # ---------------------------------------------------------------- dry run

    def test_dry_run_writes_nothing(self):
        out = self.migrate("--dry-run")
        self.assertEqual(snapshot(self.dest), self.before)
        self.assertIn("would write Snakefile.new", out)
        self.assertIn("+++ Snakefile.new", out)
        out = self.migrate("--dry-run", "--apply", "--seed=01=" + BASELINE)
        self.assertEqual(snapshot(self.dest), self.before)
        self.assertIn("would install", out)
        self.assertIn("would seed outputs/01_valid-tags/ from outputs/{}/: 3 file(s)".format(BASELINE), out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "analysis", ".trim-hto.scaffold.lock")))

    # ---------------------------------------------------------------- apply

    def test_apply_swaps_and_keeps_the_originals(self):
        out = self.migrate("--apply")
        self.assertIn("installed Snakefile, run.sh, run.sbatch, _quarto.yml (originals kept as *.pre-0.27)", out)
        for name in ("Snakefile", "run.sh", "run.sbatch", "_quarto.yml"):
            self.assertEqual(snapshot(self.dest)[name + ".pre-0.27"], self.before[name], name)  # the original, byte for byte
            self.assertFalse(os.path.exists(self.path(name + ".new")), name)
        self.assertIn("outputs/01_valid-tags/01_valid-tags.rds", read(self.path("Snakefile")))
        self.assertEqual(read(self.path("run.sh")), read(os.path.join(TEMPLATES, "run.sh")).replace("@@NAME@@", "trim-hto"))
        self.assertTrue(os.access(self.path("run.sh"), os.X_OK))
        self.assertTrue(os.path.isfile(self.path("MIGRATE.md")))
        # run folders are not touched, no marker without --seed
        self.assertFalse(os.path.exists(self.path("outputs", ".layout")))
        self.assertTrue(os.path.isfile(self.path("outputs", BASELINE, "RUN.txt")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "analysis", ".trim-hto.scaffold.lock")))  # the scaffold's flock

    def test_apply_installs_the_snakefile_the_user_edited(self):
        self.migrate()
        edited = self.new_snakefile().replace('"outputs/notes/readme.txt"', '"outputs/01_valid-tags/tables/01_tags_per_donor.tsv"')
        with open(self.path("Snakefile.new"), "w") as handle:
            handle.write(edited)
        self.migrate("--apply")
        self.assertEqual(read(self.path("Snakefile")), edited)
        self.assertEqual(snapshot(self.dest)["Snakefile.pre-0.27"], self.before["Snakefile"])

    def test_apply_refuses_to_overwrite_a_kept_original(self):
        with open(self.path("run.sh.pre-0.27"), "w") as handle:
            handle.write("older\n")
        before = snapshot(self.dest)
        self.refused("--apply", fragment="run.sh.pre-0.27 exists already")
        self.assertEqual(snapshot(self.dest), before)

    # ---------------------------------------------------------------- reruns, stale files, odd rules

    def edit_snakefile(self, old, new, count=1):
        text = read(self.path("Snakefile"))
        self.assertIn(old, text)
        with open(self.path("Snakefile"), "w") as handle:
            handle.write(text.replace(old, new, count))

    def test_rerun_keeps_an_edited_new_file(self):
        self.migrate()
        self.migrate()  # nothing edited: the same text again is fine
        with open(self.path("Snakefile.new"), "a") as handle:
            handle.write("# my edit\n")
        before = snapshot(self.dest)
        self.refused(fragment="Snakefile.new differs from a fresh migration")
        self.assertEqual(snapshot(self.dest), before)
        self.migrate("--dry-run")  # a dry run writes nothing, so it does not refuse
        os.unlink(self.path("Snakefile.new"))
        self.migrate()
        self.assertNotIn("# my edit", self.new_snakefile())

    def test_apply_refuses_when_the_original_changed_after_the_new_file(self):
        self.migrate()
        with open(self.path("Snakefile"), "a") as handle:
            handle.write("# LATE EDIT TO ORIGINAL\n")
        later = os.stat(self.path("Snakefile.new")).st_mtime + 10
        os.utime(self.path("Snakefile"), (later, later))
        before = snapshot(self.dest)
        self.refused("--apply", fragment="Snakefile changed after Snakefile.new was written")
        self.assertEqual(snapshot(self.dest), before)

    def test_apply_diff_shows_the_edited_new_file(self):
        self.migrate()
        with open(self.path("Snakefile.new"), "a") as handle:
            handle.write("# USER FIX\n")
        self.assertIn("+# USER FIX", self.migrate("--apply"))

    def test_apply_failure_keeps_the_new_files(self):
        self.migrate()
        with open(self.path("Snakefile.new"), "a") as handle:
            handle.write("# USER EDIT\n")
        os.chmod(self.path("_quarto.yml.new"), 0)
        if os.access(self.path("_quarto.yml.new"), os.R_OK):
            self.skipTest("permissions are not enforced here (root)")
        self.refused("--apply", fragment="Permission denied")
        self.assertIn("# USER EDIT", read(self.path("Snakefile.new")))
        self.assertTrue(os.path.isfile(self.path("run.sh.new")))
        self.assertEqual(read(self.path("Snakefile")), read(os.path.join(FIXTURE, "Snakefile")))
        os.chmod(self.path("_quarto.yml.new"), 0o644)

    def test_install_failure_restores_originals_and_keeps_new_files(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("new_analysis_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.migrate()
        with self.assertRaises(OSError):
            module.install(self.dest, {"Snakefile": "x\n", "missing/dir/file": "y\n"})
        self.assertEqual(read(self.path("Snakefile")), read(os.path.join(FIXTURE, "Snakefile")))
        self.assertTrue(os.path.isfile(self.path("Snakefile.new")))

    def test_qmd_render_in_other_forms_is_rewritten_or_flagged(self):
        self.edit_snakefile("render {input.script:q} > {log:q} 2>&1\"\n\n\n# the figures",
                            "render {input.script} > /dev/null\"\n\n\n# the figures")
        self.migrate("--dry-run")
        out = self.migrate("--dry-run")
        self.assertIn("render {input.script} --output-dir outputs/10_gate-figures > /dev/null && "
                      "mv outputs/10_gate-figures/code/10_gate-figures.html outputs/10_gate-figures/10_gate-figures.html", out)
        self.assertIn("the render command had another form", out)
        self.edit_snakefile("{QUARTO:q} render {input.script:q} > {log:q} 2>&1\"\n", "echo no render > {log:q}\"\n")
        flagged = [l for l in self.migrate("--dry-run").split("\n") if "13_timepoint-figures.html" in l and "no render command" in l]
        self.assertEqual(len(flagged), 1, flagged)

    def test_a_note_does_not_hide_a_live_out_reference(self):
        self.edit_snakefile('        script="code/01_valid-tags.R",\n',
                            '        script="code/01_valid-tags.R",\n        many=expand(f"{OUT}/tables/{{s}}.tsv", OUT=OUT, s=["a", "b"]),\n')
        self.migrate()
        line = next(l for l in self.new_snakefile().split("\n") if "many=expand" in l)
        self.assertIn("still names OUT, BASE or RUN", line)
        self.assertEqual(line.count("# MIGRATE: check:"), 1, line)

    def test_a_directory_output_keeps_its_own_folder(self):
        self.edit_snakefile('        f"{OUT}/tables/01_tags_per_donor.tsv",\n',
                            '        f"{OUT}/tables/01_tags_per_donor.tsv",\n        d=directory(f"{OUT}/01_dir"),\n')
        self.migrate()
        text = self.new_snakefile()
        self.assertIn('d=directory("outputs/01_valid-tags/01_dir"),', text)
        self.assertIn('"outputs/01_valid-tags/01_valid-tags.rds",', text)  # a plain file named like the step still collapses

    def test_rules_that_share_a_script_share_a_log_and_are_flagged(self):
        with open(self.path("Snakefile"), "a") as handle:
            handle.write('\n\nrule step01_again:\n    input:\n        script="code/01_valid-tags.R",\n    output:\n'
                         '        f"{OUT}/tables/again.tsv",\n    log:\n        f"{OUT}/logs/01_valid-tags.log",\n    shell:\n'
                         '        "true"\n')
        self.migrate()
        flagged = [l for l in self.new_snakefile().split("\n") if "gets the same log" in l]
        self.assertEqual(len(flagged), 2, flagged)  # both rules' logs

    def test_report_lists_reads_of_other_steps_files_by_name(self):
        with open(self.path("code", "09_extra.R"), "w") as handle:
            handle.write('x <- readRDS(file.path(RUN, "06_tag-dominance.rds"))\ny <- read.delim(file.path(RUN, "tables", "09_own.tsv"))\n')
        self.migrate()
        report = read(self.path("MIGRATE.md"))
        self.assertIn("`code/09_extra.R:1`", report)
        self.assertIn("(file of step 06)", report)
        self.assertNotIn("`code/09_extra.R:2`", report)  # its own step's file

    # ---------------------------------------------------------------- seed

    def test_seed_copies_only_declared_outputs_and_skips_existing(self):
        os.makedirs(self.path("outputs", "01_valid-tags", "tables"))
        with open(self.path("outputs", "01_valid-tags", "tables", "01_valid_tags.tsv"), "w") as handle:
            handle.write("mine\n")
        out = self.migrate("--apply", "--seed=01={},01b_scar-denoise={},06_tag-dominance={}".format(BASELINE, BASELINE, GATECHECK))
        self.assertIn("seeded outputs/01_valid-tags/ from outputs/{}/: 2 file(s), 1 already there".format(BASELINE), out)
        self.assertIn("seeded outputs/01b_scar-denoise/ from outputs/{}/: 4 file(s), 0 already there".format(BASELINE), out)
        step1 = self.path("outputs", "01_valid-tags")
        self.assertEqual(sorted(os.listdir(step1)), ["01_valid-tags.rds", "tables"])  # not the sessioninfo, not logs/
        self.assertEqual(read(os.path.join(step1, "tables", "01_valid_tags.tsv")), "mine\n")  # kept
        self.assertEqual(read(os.path.join(step1, "tables", "01_tags_per_donor.tsv")), "tag\tn\nA\t1\n")
        scar = self.path("outputs", "01b_scar-denoise")
        self.assertEqual(sorted(os.listdir(os.path.join(scar, "B1a"))), ["ambient_grid.tsv", "run_info.json"])  # no ambient_profile
        self.assertEqual(sorted(os.listdir(os.path.join(scar, "B1b"))), ["ambient_grid.tsv", "run_info.json"])
        step6 = self.path("outputs", "06_tag-dominance")
        self.assertEqual(sorted(os.listdir(step6)), ["06_tag-dominance.rds", "tables"])
        # copies, never moves: every run folder file is still there, byte for byte
        after = snapshot(self.dest)
        for rel, digest in self.before.items():
            if rel.startswith("outputs"):
                self.assertEqual(after.get(rel), digest, rel)
        # the marker and the log entry
        self.assertEqual(read(self.path("outputs", ".layout")), "layout: steps\nversion: 1\n")
        log = read(self.path("logs", "CHANGES.md"))
        self.assertIn(" migrated ok\n", log)
        self.assertIn("- outputs/06_tag-dominance/ (seeded: copied 2 file(s) from outputs/{}/".format(GATECHECK), log)
        self.assertTrue(log.startswith("# Change log"))
        self.assertEqual(ap.last_change(self.dest).split()[3:], ["migrated", "ok"])
        # the resolver lists the step folders first and the run folders after
        found = ap.runs(self.dest)
        self.assertEqual([r["layout"] for r in found], ["steps", "run", "run"])
        self.assertEqual(ap.step_dirs(found[0]), ["01_valid-tags", "01b_scar-denoise", "06_tag-dominance"])

    def test_seed_again_after_apply_adds_steps_and_skips_what_exists(self):
        self.migrate("--apply", "--seed=01={}".format(BASELINE))
        out = self.migrate("--seed=01={},06={}".format(BASELINE, GATECHECK))
        self.assertIn("was migrated already; seeding only", out)
        self.assertIn("seeded outputs/01_valid-tags/ from outputs/{}/: 0 file(s), 3 already there".format(BASELINE), out)
        self.assertIn("seeded outputs/06_tag-dominance/ from outputs/{}/: 2 file(s)".format(GATECHECK), out)
        self.assertEqual(read(self.path("logs", "CHANGES.md")).count(" migrated ok\n"), 2)
        self.refused(fragment="was migrated already")  # without --seed there is nothing left to do

    def test_seed_reports_a_declared_output_the_run_lacks(self):
        out = self.migrate("--apply", "--seed=02={}".format(BASELINE))
        self.assertIn("seeded outputs/02_restricted-calls/ from outputs/{}/: 0 file(s)".format(BASELINE), out)
        self.assertIn("no file in the run for declared output 02_restricted-calls.rds", out)

    def test_seed_refusals(self):
        self.refused("--seed=01=" + BASELINE, fragment="--seed goes with --apply")
        self.refused("--apply", "--seed=99=" + BASELINE, fragment="matches 0 rules")
        self.refused("--apply", "--seed=01=run_20990101_nope", fragment="outputs/run_20990101_nope is not a run folder")
        self.refused("--apply", "--seed=01", fragment="step=run pairs")
        self.refused("--apply", "--seed=01={},01_valid-tags={}".format(BASELINE, GATECHECK), fragment="names step 01_valid-tags twice")
        self.assertEqual(snapshot(self.dest), self.before)

    # ---------------------------------------------------------------- refusals

    def test_refuses_without_a_snakefile(self):
        os.unlink(self.path("Snakefile"))
        self.refused(fragment="has no Snakefile")

    def test_refuses_the_steps_layout(self):
        with open(self.path("outputs", ".layout"), "w") as handle:
            handle.write("layout: steps\nversion: 1\n")
        before = snapshot(self.dest)
        self.refused(fragment="already in the step-folder layout")
        self.refused("--apply", fragment="already in the step-folder layout")
        self.assertEqual(snapshot(self.dest), before)

    def test_refuses_a_snakefile_that_is_not_run_based(self):
        with open(self.path("Snakefile"), "w") as handle:
            handle.write("rule all:\n    input:\n        \"outputs/01_a/x.rds\",\n")
        self.refused(fragment="not a run-folder analysis")

    def test_refuses_symlinked_code_and_outputs(self):
        elsewhere = os.path.join(self.root, "elsewhere")
        shutil.move(self.path("code"), elsewhere)
        os.symlink(elsewhere, self.path("code"))
        self.refused(fragment="analysis/trim-hto/code is a symlink")
        os.unlink(self.path("code"))
        shutil.move(elsewhere, self.path("code"))
        shutil.move(self.path("outputs"), elsewhere)
        os.symlink(elsewhere, self.path("outputs"))
        self.refused("--apply", fragment="analysis/trim-hto/outputs is a symlink")
        self.assertFalse(os.path.exists(self.path("Snakefile.new")))

    def test_refuses_a_missing_folder_and_stray_flags(self):
        proc = run(self.root, "--dest=analysis/nope", "--migrate")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not an existing analysis folder", proc.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, "analysis", "nope")))
        self.refused("--steps=01_a.R", fragment="takes --dest, --seed, --apply and --dry-run only")
        proc = run(self.root, "--dest=analysis/trim-hto", "--apply")
        self.assertIn("--apply and --seed go with --migrate", proc.stdout)
        self.assertEqual(snapshot(self.dest), self.before)

    # ---------------------------------------------------------------- real Snakemake

    @unittest.skipUnless(snakemake_path(), "no snakemake (set MX_SNAKEMAKE)")
    def test_new_snakefile_parses_in_real_snakemake(self):
        self.migrate()
        os.makedirs(self.path("outputs", "notes"))  # the one path that has no producer: the user's to fix
        with open(self.path("outputs", "notes", "readme.txt"), "w") as handle:
            handle.write("note\n")
        env = dict(os.environ, XDG_CACHE_HOME=os.path.join(self.root, "cache"))
        proc = subprocess.run([snakemake_path(), "-n", "--cores", "1", "--snakefile", "Snakefile.new"], cwd=self.dest, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        for rule in ("step01_valid_tags", "step01b_scar_denoise", "step06_tag_dominance", "step13_figures"):  # what `all` needs
            self.assertIn(rule, proc.stdout)
        self.assertIn("outputs/13_timepoint-figures/13_timepoint-figures.html", proc.stdout)
        self.assertIn("B1b", proc.stdout)  # the batch wildcard expands from the constraint list
        # after --apply the same file is the Snakefile; the steps `all` skips plan too when named
        self.migrate("--apply")
        proc = subprocess.run([snakemake_path(), "-n", "--cores", "1", "step02_restricted_calls", "step10_gate_figures"],
                              cwd=self.dest, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("outputs/02_restricted-calls/02_restricted-calls.rds", proc.stdout)
        self.assertIn("outputs/10_gate-figures/10_gate-figures.html", proc.stdout)


if __name__ == "__main__":
    unittest.main()
