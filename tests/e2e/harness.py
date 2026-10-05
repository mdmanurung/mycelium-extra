"""End-to-end harness: drive the plugin's hooks and skills against a copy of the fixture project.

Stdlib only, Python 3.6 grammar. See docs/design/c1-fixture-project.md, section 6.

The hooks are run as hooks/hooks.json registers them (`python3 hooks/gate_run.py <entry>`), with
the event shapes Claude Code sends: a successful Bash call fires PostToolUse, whose tool_response
carries no exit code; a failed one fires PostToolUseFailure, with a top-level `error` whose first
line is `Exit code N`. The failure event reaches the gate only if hooks.json registers it.
"""

import base64
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.dirname(HERE)
REPO = os.path.dirname(TESTS)
FIXTURE = os.path.join(TESTS, "fixtures", "mycelium-project")
EXPECTED = os.path.join(HERE, "expected")
PLANS = os.path.join(HERE, "plans")
HOOKS_JSON = os.path.join(REPO, "hooks", "hooks.json")
SKILLS = os.path.join(REPO, "skills")
# The gate entry point and verify source the harness runs; ablate.py points them at patched copies.
GATE_RUN = os.path.join(REPO, "hooks", "gate_run.py")
VERIFY = os.path.join(SKILLS, "verify", "scripts", "verify.py")
ANALYSIS = "analysis/vaccine-response"
SCRIPTS = [ANALYSIS + "/scripts/01_select_samples.py", ANALYSIS + "/scripts/02_paired_test.py",
           ANALYSIS + "/scripts/03_summary.R"]
OUTPUTS = [ANALYSIS + "/outputs/samples_used.tsv", ANALYSIS + "/outputs/de_results.tsv",
           ANALYSIS + "/outputs/summary.tsv"]

TOLERANCE = 5.0  # verify's clock-skew allowance (skills/verify/scripts/verify.py, TOLERANCE)
SCRUB = ("CONDA_PREFIX", "CONDA_DEFAULT_ENV", "VIRTUAL_ENV", "PIXI_ENVIRONMENT_NAME", "CLAUDE_PLUGIN_ROOT")
IDENTITY = {"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.org",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.org",
            "GIT_AUTHOR_DATE": "2026-09-01T09:00:00Z", "GIT_COMMITTER_DATE": "2026-09-01T09:00:00Z"}
# Gate entry argument -> the Claude Code event it serves, when hooks.json does not say.
EVENTS = {"tool": "PreToolUse", "prompt": "UserPromptSubmit", "post": "PostToolUse", "stop": "Stop"}
SESSION = "e2e-session-1"


class HarnessError(AssertionError):
    """A step of the chain did not behave as the plugin documents; the message says which."""


def plan_text(name="baseline"):
    with open(os.path.join(PLANS, name + "_plan.md"), encoding="utf-8") as handle:
        return handle.read()


def contract_text(name="baseline"):
    with open(os.path.join(PLANS, name + "_contract.json"), encoding="utf-8") as handle:
        return handle.read()


def expected(name):
    with open(os.path.join(EXPECTED, name), encoding="utf-8") as handle:
        return json.load(handle) if name.endswith(".json") else handle.read()


def registered_events(path=HOOKS_JSON):
    """{Claude Code event: gate entry argument} for every gate hook hooks.json registers now."""
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    found = {}
    for event, groups in (config.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks") or []:
                match = re.search(r"hooks/gate(?:_run)?\.py\"?\s+(\w+)", hook.get("command", ""))
                if match:
                    found[event] = match.group(1)
    return found


def git_available():
    return shutil.which("git") is not None


def rscript_dirs():
    return [d for d in os.environ.get("PATH", "").split(os.pathsep)
            if d and os.path.isfile(os.path.join(d, "Rscript"))]


def iso(epoch):
    return datetime.datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sh_quote(text):
    if re.match(r"^[\w@%+=:,./-]+$", text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


class Result(object):
    """One agent Bash call: the PreToolUse reply, the run, the post reply, and new receipts."""

    def __init__(self, command, pre=None, denied=False, code=None, stdout="", stderr="", post=None,
                 receipts=None, simulated=False, event=None):
        self.command, self.pre, self.denied, self.code = command, pre, denied, code
        self.stdout, self.stderr, self.post = stdout, stderr, post
        self.receipts = receipts or []
        self.simulated, self.event = simulated, event

    @property
    def reason(self):
        return ((self.pre or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


class Project(object):
    """A temporary, gated copy of the fixture project. Call `close()` (or pass it to addCleanup)."""

    def __init__(self, tmp, r=True):
        self.tmp = tmp
        self.root = os.path.join(tmp, "project")
        self.bin = os.path.join(tmp, "bin")
        self.home = os.path.join(tmp, "home")
        self.session = SESSION
        self.r = r
        self.events = registered_events()
        self.runs = []  # (epoch, command, absolute script path or None) of every Python or R run
        self.log = []   # readable trace of the chain, for failure messages
        self.init_output = ""

    # ------------------------------------------------------------ setup

    @classmethod
    def fresh(cls, r=None):
        """r=None: use R if Rscript is on PATH; r=False: hide R (03 then runs as an effect)."""
        if r is None:
            r = bool(rscript_dirs())
        project = cls(tempfile.mkdtemp(prefix="mx-e2e-"), r=r)
        try:
            project._setup()
        except Exception:
            project.close()
            raise
        return project

    def _setup(self):
        shutil.copytree(FIXTURE, self.root)
        os.makedirs(self.bin)
        os.makedirs(self.home)
        self.write_fakes()
        old = time.time() - 3600
        for folder, _, files in os.walk(self.root):
            for name in files:
                os.utime(os.path.join(folder, name), (old, old))
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture project")
        self.init_output = self.init()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "mycelium-extra init")

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_fakes(self, sacct=None, scilintr="", scilintr_code=0):
        """sacct prints one `id|state|exit|start|end` line; scilintr and Rscript-lint print `scilintr`."""
        now = time.time()
        line = sacct or "4242|COMPLETED|0:0|{}|{}".format(
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 600)),
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)))
        lint = "#!/bin/sh\nprintf '%s' {}\nexit {}\n".format(sh_quote(scilintr) if scilintr else "''",
                                                               scilintr_code)
        fakes = {"sacct": "#!/bin/sh\necho {}\n".format(sh_quote(line)), "scilintr": lint, "Rscript-lint": lint}
        for name, body in fakes.items():
            path = os.path.join(self.bin, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(body)
            os.chmod(path, 0o755)

    def env(self):
        env = {k: v for k, v in os.environ.items() if k not in SCRUB}
        system = [d for d in env.get("PATH", "/usr/bin:/bin").split(os.pathsep) if d]
        if not self.r:
            hidden = [d for d in system if os.path.isfile(os.path.join(d, "Rscript"))]
            system = [d for d in system if d not in hidden]
            for needed in ("python3", "git", "bash"):  # keep these if they lived next to R
                if not any(os.path.isfile(os.path.join(d, needed)) for d in system):
                    raise HarnessError("hiding R ({}) also hides {}".format(", ".join(hidden), needed))
        env.update(IDENTITY)
        env.update({"PATH": os.pathsep.join([self.bin] + system), "HOME": self.home, "TZ": "UTC",
                    "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_NOSYSTEM": "1"})
        return env

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def git(self, *args):
        proc = subprocess.Popen(("git",) + args, cwd=self.root, env=self.env(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        if proc.returncode != 0:
            raise HarnessError("git {} failed: {}".format(" ".join(args), err.decode("utf-8", "replace")))
        return out.decode("utf-8")

    def shell(self, command):
        """Run `command` with bash from the project root; returns (code, stdout, stderr)."""
        proc = subprocess.Popen(["bash", "-c", command], cwd=self.root, env=self.env(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def edit(self, rel, change):
        """Replace a file's text with change(text); fails if nothing changed, so a stale mutation shows."""
        with open(self.path(rel), encoding="utf-8") as handle:
            text = handle.read()
        new = change(text)
        if new == text:
            raise HarnessError("editing {} changed nothing".format(rel))
        with open(self.path(rel), "w", encoding="utf-8") as handle:
            handle.write(new)
        self.log.append("edited " + rel)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def init(self):
        """skills/init in its documented stdin form (no gate yet, so no PreToolUse check)."""
        script = os.path.join(SKILLS, "init", "scripts", "gate_init.py")
        code, out, err = self.shell("python3 - < {}".format(sh_quote(script)))
        if code != 0:
            raise HarnessError("init exited {}: {}".format(code, err))
        return out + err

    # ------------------------------------------------------------ hooks

    def hook(self, entry, payload, cwd=None):
        """Run the gate as hooks.json does, for gate entry `entry` (tool, prompt, post, stop, ...)."""
        event = dict(payload, session_id=self.session, cwd=cwd or self.root)
        event.setdefault("hook_event_name", EVENTS.get(entry, entry))
        proc = subprocess.Popen([sys.executable, GATE_RUN, entry],
                                cwd=cwd or self.root, env=self.env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(json.dumps(event, ensure_ascii=False).encode("utf-8"))  # raw UTF-8, as Claude Code sends it
        if proc.returncode != 0:
            raise HarnessError("gate {} exited {}: {}".format(entry, proc.returncode, err.decode("utf-8")))
        text = out.decode("utf-8").strip()
        result = json.loads(text) if text else None
        message = (result or {}).get("systemMessage", "")
        if "gate error" in message:
            raise HarnessError("gate {} broke: {}".format(entry, message))
        return result

    def pre_bash(self, command):
        return self.hook(self.events.get("PreToolUse", "tool"),
                         {"tool_name": "Bash", "tool_input": {"command": command}, "hook_event_name": "PreToolUse"})

    @staticmethod
    def denied(result):
        return bool(result) and (result.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"

    def approve(self, text):
        """Stop hook with the plan, then the prompt `approve plan <hash>`; returns (hash, notice, reply)."""
        notice = self.hook(self.events.get("Stop", "stop"),
                           {"last_assistant_message": text, "stop_hook_active": False, "hook_event_name": "Stop"})
        message = (notice or {}).get("systemMessage", "")
        match = re.search(r"approve plan ([0-9a-f]{8})", message)
        if not match:
            raise HarnessError("the Stop hook offered no `approve plan <hash>`; it said: {!r}".format(message))
        digest = match.group(1)
        reply = self.hook(self.events.get("UserPromptSubmit", "prompt"),
                          {"prompt": "approve plan " + digest, "hook_event_name": "UserPromptSubmit"})
        self.log.append("approved plan {}".format(digest))
        return digest, message, reply

    def read_jsonl(self, name):
        path = self.path(".mycelium-extra", name)
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def receipts(self):
        return self.read_jsonl("receipts.jsonl")

    def approval(self, digest):
        """The gate's approval record for `digest`, or None."""
        path = self.path(".mycelium-extra", "approvals", digest + ".json")
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    # ------------------------------------------------------------ agent actions

    def agent_bash(self, command, effect=None, response="claude"):
        """One agent Bash call: PreToolUse; run it (or `effect`); PostToolUse or PostToolUseFailure.

        response="claude": the shapes Claude Code sends. Success: PostToolUse, tool_response
        {stdout, stderr, interrupted, isImage}, no exit code. Failure: PostToolUseFailure with
        `error` = "Exit code N\\n<stderr>", sent only if hooks.json registers that event.
        response="legacy": PostToolUse with {stdout, stderr, exit_code} whatever the result.
        response="bare": PostToolUse's tool_response with no hook_event_name, as an older host sends.
        `effect(project)` stands in for a command the sandbox cannot run; it returns stdout.
        """
        before = len(self.receipts())
        pre = self.pre_bash(command)
        if self.denied(pre):
            self.log.append("DENIED: {}".format(command))
            return Result(command, pre=pre, denied=True)
        started = time.time()
        if effect is not None:
            code, out, err = 0, effect(self) or "", ""
            self.log.append("simulated (effect): {}".format(command))
        else:
            code, out, err = self.shell(command)
            self.log.append("ran (exit {}): {}".format(code, command))
        script = script_of(command)
        if script is not False:
            self.runs.append((started, command, self.path(script) if script else None))
        tool_input = {"command": command}
        if response == "legacy":
            name = "PostToolUse"
            payload = {"tool_response": {"stdout": out, "stderr": err, "exit_code": code}}
        elif response == "bare":
            name = "PostToolUse"
            payload = {"tool_response": {"stdout": out, "stderr": err}}
        elif code == 0:
            name = "PostToolUse"
            payload = {"tool_response": {"stdout": out, "stderr": err, "interrupted": False, "isImage": False}}
        else:
            name = "PostToolUseFailure"
            payload = {"error": "Exit code {}\n{}".format(code, (err or out).strip()), "is_interrupt": False,
                       "duration_ms": int((time.time() - started) * 1000)}
        payload.update({"tool_name": "Bash", "tool_input": tool_input,
                        "hook_event_name": None if response == "bare" else name})
        entry = self.events.get(name)
        post = self.hook(entry, payload) if entry else None
        if entry is None:
            self.log.append("{} not registered in hooks.json; no post hook ran".format(name))
        return Result(command, pre=pre, code=code, stdout=out, stderr=err, post=post,
                      receipts=self.receipts()[before:], simulated=effect is not None, event=name)

    def run_step(self, script, prefix=""):
        """One planned step as the agent runs it; 03 is an effect copying expected/summary.tsv without R."""
        if script.endswith(".R"):
            return self.agent_bash(prefix + "Rscript " + script, effect=None if self.r else copy_summary)
        return self.agent_bash(prefix + "python3 " + script)

    def run_plan(self, text=None, scripts=SCRIPTS):
        """Approve `text` (default: the baseline plan), run `scripts`, space the outputs, and write
        Mycelium's lineage. Returns (digest, results); a denied or failed step is left to the caller."""
        digest = self.approve(text or plan_text())[0]
        results = [self.run_step(script) for script in scripts]
        pairs = [(out_of(s), r.receipts[0]) for s, r in zip(scripts, results)
                 if r.receipts and out_of(s) and os.path.isfile(self.path(out_of(s)))]
        self.space_outputs(pairs)
        self.lineage()
        return digest, results

    def skill(self, name, documented, run=None):
        """A skill command as the agent sends it: PreToolUse must stay silent for `documented`.

        Then `run` (default: `documented`) runs with bash from the project root, and the post
        hook sees it as Claude Code would. Returns (code, stdout, stderr).
        """
        pre = self.pre_bash(documented)
        if pre:
            raise HarnessError("the gate did not stay silent for {}'s documented command:\n{}\n{}".format(
                name, documented, json.dumps(pre, indent=1)))
        code, out, err = self.shell(run or documented)
        self.log.append("skill {} (exit {})".format(name, code))
        tool_response = {"stdout": out, "stderr": err, "interrupted": False, "isImage": False}
        if code == 0 and self.events.get("PostToolUse"):
            self.hook(self.events["PostToolUse"], {"tool_name": "Bash", "tool_input": {"command": documented},
                                                   "tool_response": tool_response})
        return code, out, err

    def stdin_skill(self, name, script, args):
        """`python3 - ARGS < <skill-dir>/scripts/SCRIPT`, the documented form of most skills."""
        path = os.path.join(SKILLS, name, "scripts", script)
        return self.skill(name, "python3 - {} < {}".format(args, sh_quote(path)))

    def data_contract(self, contract):
        """data-contract-check as SKILL.md documents it: a process-substituted heredoc, run with bash -c."""
        script = os.path.join(SKILLS, "data-contract-check", "scripts", "data_contract_check.py")
        command = "python3 - --contract <(cat <<'EOF'\n{}\nEOF\n) < {}".format(contract.strip(), sh_quote(script))
        return self.skill("data-contract-check", command)

    def verify_command(self, *args):
        """(documented form, run form) of a verify call; the run form adds --repo and the fakes."""
        script = sh_quote(VERIFY)
        plugin = sh_quote(os.path.join(SKILLS, "verify") + "/../..")
        words = " ".join(sh_quote(a) for a in args)
        documented = "python3 - --plugin-root {} {} < {}".format(plugin, words, script)
        run = "python3 - --plugin-root {} --repo {} --sacct {} --scilintr {} --rscript {} {} < {}".format(
            plugin, sh_quote(self.root), sh_quote(os.path.join(self.bin, "sacct")),
            sh_quote(os.path.join(self.bin, "scilintr")), sh_quote(os.path.join(self.bin, "Rscript-lint")),
            words, script)
        return documented, run

    def verify(self, *args):
        documented, run = self.verify_command(*args)
        return self.skill("verify", documented, run)

    # ------------------------------------------------------------ Mycelium's records

    def lineage(self, runs=None):
        """.living/log/data-lineage/<sid>.json as Mycelium's tracker writes it: every Python or R run."""
        runs = self.runs if runs is None else runs
        actions = [{"ts": iso(ts), "script": script, "bash_cmd": command} for ts, command, script in runs]
        folder = self.path(".living", "log", "data-lineage")
        if not os.path.isdir(folder):
            os.makedirs(folder)
        path = os.path.join(folder, self.session + ".json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"session_id": self.session, "actions": actions}, handle, indent=1)
        return path

    def snakemake_record(self, output, rule, inputs, shellcmd, incomplete=False, start=None, end=None,
                         workdir=""):
        """One <workdir>/.snakemake/metadata/<base64 name> record, in the shape test_verify.py uses;
        `output` is relative to `workdir`, as Snakemake names it."""
        end = end or time.time()
        start = start or end - 1
        name = base64.b64encode(output.encode("utf-8")).decode("ascii")
        folder = self.path(workdir, ".snakemake", "metadata")
        if not os.path.isdir(folder):
            os.makedirs(folder)
        record = {"rule": rule, "input": inputs, "shellcmd": shellcmd, "incomplete": incomplete,
                  "starttime": start, "endtime": end}
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        return record

    # ------------------------------------------------------------ time (design 6.4)

    def space_outputs(self, pairs):
        """Make each output's mtime credit the run that wrote it, without sleeping.

        verify ties an output to the EARLIEST receipt with ts >= mtime - TOLERANCE, and the gate
        stamps receipts with time.time(), so runs a few hundred ms apart all qualify and the first
        wins. For each (output, receipt) pair whose mtime would also credit an earlier receipt, the
        mtime moves to the middle of (previous receipt ts + TOLERANCE, receipt ts + TOLERANCE].
        """
        stamps = sorted(r["ts"] for r in self.receipts())
        for rel, receipt in pairs:
            full = self.path(rel)
            mtime = os.stat(full).st_mtime
            earlier = [t for t in stamps if t < receipt["ts"]]
            low, high = (earlier[-1] + TOLERANCE if earlier else None), receipt["ts"] + TOLERANCE
            if mtime > high:
                raise HarnessError("{} was written more than {} s after its run's receipt".format(rel, TOLERANCE))
            if low is None or mtime > low:
                continue
            if high - low < 0.02:
                raise HarnessError("receipts {:.3f} s apart: too close to tell the runs apart".format(high - low))
            target = (low + high) / 2.0
            os.utime(full, (target, target))
            self.log.append("mtime of {} set to its receipt + {:.3f} s".format(rel, target - receipt["ts"]))

    def fill_ledger(self, digest, finding="vaccine-response.md"):
        """F-001's Evidence Ledger Run/Session cell, in the form the post hook suggests."""
        path = self.path(".living", "findings", finding)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if "RUN-SESSION" not in text:
            raise HarnessError("{} has no RUN-SESSION placeholder".format(finding))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace("RUN-SESSION", "{}; plan {}".format(self.session, digest)))


def script_of(command):
    """Script a Python or R command runs; None for inline `-c`/`-e`; False if not Python or R."""
    words = command.split()
    if not words or not re.match(r"^(python3?|Rscript)$", os.path.basename(words[0])):
        return False
    for word in words[1:]:
        if word in ("-c", "-e"):
            return None
        if word == "-":
            return False  # stdin form: Mycelium's hooks do not see it
        if re.search(r"\.(py|R)$", word):
            return word
    return False


def out_of(script):
    """The output a planned step writes (the steps and outputs share their order)."""
    return OUTPUTS[SCRIPTS.index(script)] if script in SCRIPTS else None


def copy_summary(project):
    """Effect for `Rscript .../03_summary.R` when R is absent: the generator's twin of its output."""
    shutil.copyfile(os.path.join(EXPECTED, "summary.tsv"), project.path(ANALYSIS, "outputs", "summary.tsv"))
    return ""


def status_line(text):
    lines = [l for l in text.strip().splitlines() if l.startswith("Verify status:")]
    return lines[-1] if lines else None
