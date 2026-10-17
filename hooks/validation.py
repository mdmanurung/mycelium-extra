"""Validation bindings and exact-execution declarations in an approved plan (roadmap C06, C07).

Two optional comment blocks in the plan text, both `version` 1 and both frozen by the plan's approval:

    <!-- validation-bindings {"version": 1, "checks": [{"id": "V1", "plan_row": "3", "required": true,
         "defined_by": "researcher-approved", "test_paths": ["analysis/x/tests/expect.tsv"],
         "invocation": ["python", "analysis/x/tests/check.py"], "evidence_path": "analysis/x/outputs/check.json"}]} -->
    <!-- exact-execution {"version": 1, "steps": [{"row": "2", "argv": ["python", "analysis/x/fit.py", "--seed", "1"],
         "cwd": ".", "env": {}, "operational": ["--threads"]}]} -->

This module reads and checks the blocks and compares a launched command with a declared one. It never runs a
command, never decides what a correct expectation is, and does not import the gate: the gate passes the plan's
row ids and the repository root. `defined_by` is what the plan says about who wrote the check; it is recorded,
not verified. Python 3.6 compatible, standard library only.
"""

import hashlib
import json
import os
import posixpath
import re

VERSION = 1
DEFINED_BY = ("agent-proposed", "researcher-approved", "independent")
CHECK_KEYS = ("id", "plan_row", "required", "defined_by", "test_paths", "invocation", "evidence_path")
STEP_KEYS = ("row", "argv", "cwd", "env", "operational")
BLOCK = r"<!--\s*{}\b(.*?)-->"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DYNAMIC = re.compile(r"[$`]")
OUT_REDIRECT = re.compile(r"^>{1,2}(&[\d-]*)?$")
MAX_PIN_BYTES = 256 * 1024 * 1024
STATE = ".mycelium-extra"


# ---------------------------------------------------------------- reading a block

def read_block(text, name, list_key):
    """(data, errors) for the `name` block of a plan: data is None when there is no block, or when it cannot be
    interpreted (errors then say why). Only the keys `version` and `list_key` are allowed."""
    found = re.findall(BLOCK.format(re.escape(name)), text, re.DOTALL)
    if not found:
        return None, []
    if len(found) > 1:
        return None, ["`{}`: the plan has {} blocks of this name; keep one".format(name, len(found))]
    try:
        data = json.loads(found[0])
    except ValueError as error:
        return None, ["`{}`: not valid JSON ({})".format(name, error)]
    if not isinstance(data, dict):
        return None, ["`{}`: the block must be a JSON object".format(name)]
    version = data.get("version")
    if isinstance(version, bool) or version != VERSION:
        return None, ["`{}`: unsupported version {!r}; this gate reads version {}".format(name, version, VERSION)]
    errors = ["`{}`: unknown key `{}`".format(name, key) for key in sorted(set(data) - set(["version", list_key]))]
    if not isinstance(data.get(list_key), list):
        errors.append("`{}`: `{}` must be a list".format(name, list_key))
        return None, errors
    return data, errors


def safe_path(root, value, what):
    """(repo-relative path, None), or (None, reason) when `value` is not a literal path inside the repository."""
    if not isinstance(value, str) or not value.strip():
        return None, "{} must be a non-empty string".format(what)
    if DYNAMIC.search(value) or value.startswith("~") or "\0" in value:
        return None, "{} `{}` is not a literal path".format(what, value)
    base = os.path.realpath(root)
    full = os.path.normpath(value if os.path.isabs(value) else os.path.join(root, value))
    for anchor in (os.path.normpath(root), base):  # the root may itself be reached through a symlink
        if full == anchor or full.startswith(anchor + os.sep):
            rel = os.path.relpath(full, anchor)
            break
    else:
        return None, "{} `{}` leaves the repository".format(what, value)
    real = os.path.realpath(full)
    if real != base and not real.startswith(base + os.sep):
        return None, "{} `{}` resolves outside the repository".format(what, value)
    rel = rel.replace(os.sep, "/")
    if rel == STATE or rel.startswith(STATE + "/"):
        return None, "{} `{}` is gate state".format(what, value)
    return rel, None


def plan_row(value, rows, what):
    """(row id as text, None) or (None, reason): the row must be one, and only one, of the plan's rows."""
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        return None, "{}: `row` must be a plan row id".format(what)
    row = str(value).strip()
    if rows.count(row) > 1:
        return None, "{}: plan row {} is ambiguous (the id repeats in the plan table)".format(what, row)
    if row not in rows:
        return None, "{}: unknown plan row {} ({})".format(what, row, "rows: " + ", ".join(rows) if rows
                                                         else "the plan has no step table")
    return row, None


def argv_list(value, what, text_ok=False):
    """(argv, None) or (None, reason): a non-empty list of strings, or (text_ok) a shell-style string."""
    if isinstance(value, str) and text_ok:
        import shlex
        try:
            value = shlex.split(value)
        except ValueError as error:
            return None, "{}: not a command ({})".format(what, error)
    if (not isinstance(value, list) or not value or not all(isinstance(a, str) and a for a in value)):
        return None, "{} must be a non-empty list of non-empty strings".format(what)
    if any(DYNAMIC.search(a) for a in value):
        return None, "{} holds a `$` or backtick substitution; write the literal value".format(what)
    return list(value), None


def file_sha256(path):
    """The file's sha256, or a string reason starting with `!` when it is missing, not a file, or too large."""
    try:
        if not os.path.isfile(path):
            return "!missing or not a file"
        if os.path.getsize(path) > MAX_PIN_BYTES:
            return "!larger than {} MiB".format(MAX_PIN_BYTES // (1 << 20))
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as error:
        return "!" + str(error)


def definition_sha256(check, file_hashes):
    """The identity of one check as approved: what it says and the content of every test file it names. A
    changed expectation changes this; an edit elsewhere in the plan does not."""
    body = dict((key, check.get(key)) for key in CHECK_KEYS)
    body["files"] = dict((path, file_hashes.get(path)) for path in check.get("test_paths") or [])
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_bindings(text, rows, root):
    """(validation, errors). `validation` is None without a block or when the block is invalid, else
    {"version": 1, "checks": [{id, plan_row, required, defined_by, test_paths, invocation (an argv list),
    evidence_path, files {path: sha256}, definition_sha256}]}. `rows` are the plan table's row ids (text).
    `evidence_path` is where the check writes its result: it must be a safe path but need not exist, and it is
    never pinned."""
    data, errors = read_block(text, "validation-bindings", "checks")
    if data is None:
        return None, errors
    checks, seen = [], set()
    for number, item in enumerate(data["checks"], 1):
        what = "check {}".format(item.get("id") if isinstance(item, dict) and isinstance(item.get("id"), str)
                                 else "#{}".format(number))
        if not isinstance(item, dict):
            errors.append("{} must be an object".format(what))
            continue
        errors += ["{}: unknown key `{}`".format(what, key) for key in sorted(set(item) - set(CHECK_KEYS))]
        errors += ["{}: missing `{}`".format(what, key) for key in CHECK_KEYS
                   if key not in item and key != "required"]
        check = {"id": item.get("id"), "required": item.get("required", True)}
        if not isinstance(check["id"], str) or not ID.match(check["id"]):
            errors.append("{}: `id` must be letters, digits, `.`, `_` or `-` (at most 64)".format(what))
        elif check["id"] in seen:
            errors.append("{}: duplicate check id".format(what))
        seen.add(check["id"])
        if not isinstance(check["required"], bool):
            errors.append("{}: `required` must be true or false".format(what))
        if "plan_row" in item:
            check["plan_row"], problem = plan_row(item["plan_row"], rows, what)
            errors += [problem] if problem else []
            if problem:
                check["plan_row"] = None
        if item.get("defined_by") not in DEFINED_BY and "defined_by" in item:
            errors.append("{}: `defined_by` must be one of {}".format(what, ", ".join(DEFINED_BY)))
        check["defined_by"] = item.get("defined_by")
        paths = item.get("test_paths")
        check["test_paths"], check["files"] = [], {}
        if "test_paths" in item and (not isinstance(paths, list) or not paths):
            errors.append("{}: `test_paths` must be a non-empty list".format(what))
        for path in paths if isinstance(paths, list) else []:
            rel, problem = safe_path(root, path, "{}: test path".format(what))
            if problem:
                errors.append(problem)
                continue
            digest = file_sha256(os.path.join(root, rel))
            if digest.startswith("!"):
                errors.append("{}: test path `{}` cannot be pinned ({})".format(what, rel, digest[1:]))
                continue
            check["test_paths"].append(rel)
            check["files"][rel] = digest
        if "invocation" in item:
            check["invocation"], problem = argv_list(item["invocation"], "{}: `invocation`".format(what), True)
            errors += [problem] if problem else []
        if "evidence_path" in item:
            check["evidence_path"], problem = safe_path(root, item["evidence_path"], "{}: evidence path".format(what))
            errors += [problem] if problem else []
        checks.append(check)
    if errors:
        return None, errors
    for check in checks:
        check["definition_sha256"] = definition_sha256(check, check["files"])
    return {"version": VERSION, "checks": checks}, []


def read_exact(text, rows, root):
    """(execution, errors). `execution` is None without a block or when it is invalid, else
    {"version": 1, "steps": [{row, argv, cwd, env, operational}]}. `argv` starts at the program (wrappers such as
    `conda run`, `srun` or `timeout` and inline `VAR=value` words are not part of it); `cwd` is repo-relative."""
    data, errors = read_block(text, "exact-execution", "steps")
    if data is None:
        return None, errors
    steps = []
    for number, item in enumerate(data["steps"], 1):
        what = "step #{}".format(number)
        if not isinstance(item, dict):
            errors.append("{} must be an object".format(what))
            continue
        errors += ["{}: unknown key `{}`".format(what, key) for key in sorted(set(item) - set(STEP_KEYS))]
        errors += ["{}: missing `{}`".format(what, key) for key in ("row", "argv") if key not in item]
        step = {"row": None, "argv": None, "cwd": ".", "env": {}, "operational": []}
        if "row" in item:
            step["row"], problem = plan_row(item["row"], rows, what)
            errors += [problem] if problem else []
        if "argv" in item:
            step["argv"], problem = argv_list(item["argv"], "{}: `argv`".format(what))
            errors += [problem] if problem else []
            if step["argv"] and step["argv"][0].startswith("-"):
                errors.append("{}: `argv` must start with the program".format(what))
        if "cwd" in item:
            step["cwd"], problem = safe_path(root, item["cwd"], "{}: cwd".format(what))
            errors += [problem] if problem else []
            if not problem and item["cwd"] in (".", "./"):
                step["cwd"] = "."
        env = item.get("env", {})
        if (not isinstance(env, dict) or not all(isinstance(k, str) and ENV_NAME.match(k) and isinstance(v, str)
                                                 and not DYNAMIC.search(v) for k, v in env.items())):
            errors.append("{}: `env` must map variable names to literal text values".format(what))
        else:
            step["env"] = env
        ops = item.get("operational", [])
        if (not isinstance(ops, list) or not all(isinstance(f, str) and f.startswith("-") and "=" not in f
                                                 and len(f) > 1 for f in ops)):
            errors.append("{}: `operational` must list flag names such as \"--threads\" (no value)".format(what))
        else:
            step["operational"] = list(ops)
        steps.append(step)
    return ({"version": VERSION, "steps": steps}, []) if not errors else (None, errors)


def changes(root, validation):
    """[(check id, path, "changed" | "missing")] for every pinned test file that is no longer as approved."""
    found = []
    for check in (validation or {}).get("checks") or []:
        for path, pinned in sorted((check.get("files") or {}).items()):
            now = file_sha256(os.path.join(root, path))
            if now != pinned:
                found.append((check["id"], path, "missing" if now.startswith("!") else "changed"))
    return found


# ---------------------------------------------------------------- comparing a launch with a declaration

def plain(token):
    while token.startswith("./"):
        token = token[2:]
    return token


def is_value(token):
    return not token.startswith("-") or re.match(r"^-\d+(\.\d+)?$", token) is not None


def drop_output_redirects(args):
    """(args without `> file`, `>> file`, `>&2` and their targets; indexes of a lone `1` or `2` just before one).
    An input redirect stays: `< other.tsv` changes what the program reads."""
    out, fds, i = [], [], 0
    while i < len(args):
        if OUT_REDIRECT.match(args[i]):
            if out and out[-1] in ("1", "2"):
                fds.append(len(out) - 1)
            i += 1 if "&" in args[i] else 2
        else:
            out.append(args[i])
            i += 1
    return out, fds


def strip_flags(args, flags, with_value):
    """`args` without the operational flags: `--flag=value` as one word, `--flag value` (a flag in `with_value`)
    as two, a bare flag as one."""
    out, i = [], 0
    while i < len(args):
        name = args[i].split("=", 1)[0]
        if name in flags and args[i].startswith("-"):
            two = "=" not in args[i] and name in with_value and i + 1 < len(args) and is_value(args[i + 1])
            i += 2 if two else 1
        else:
            out.append(args[i])
            i += 1
    return out


def argv_matches(declared, actual, cwd=".", declared_cwd=".", operational=(), env=None, actual_env=None):
    """(True, "") or (False, reason): the launched argv `actual` (from the program on, in repo-relative `cwd`)
    against the `declared` one (in `declared_cwd`). Exact after `./` is dropped and the program is compared by
    name, except the `operational` flags, whose value may differ and which may be added or removed. An
    operational flag counts as taking a separate value only if `declared` writes it with one (or with `=`);
    to add one the plan does not show, write it as `--flag=value`. A `$` or backtick in `actual` is a shell
    substitution that is not known here and never matches. `> file` is ignored; `< file` is not. Inline
    `VAR=value` words (`actual_env`) must each be declared in `env` with that value."""
    if not actual:
        return False, "no command to compare"
    for token in actual:
        if DYNAMIC.search(token):
            return False, "the command holds a shell substitution (`{}`) whose value is not known to the gate".format(token)
    if posixpath.normpath(cwd or ".") != posixpath.normpath(declared_cwd or "."):
        return False, "the folder differs (declared {}, run in {})".format(declared_cwd or ".", cwd or ".")
    if os.path.basename(actual[0]) != os.path.basename(declared[0]):
        return False, "the program differs (declared {}, run {})".format(declared[0], actual[0])
    flags = set(operational)
    with_value = set(f for f in flags for i, a in enumerate(declared) if a.split("=", 1)[0] == f and (
        "=" in a or (a == f and i + 1 < len(declared) and is_value(declared[i + 1]))))
    want = strip_flags([plain(a) for a in declared[1:]], flags, with_value)
    args, fds = drop_output_redirects([plain(a) for a in actual[1:]])
    variants = [args] + ([[a for i, a in enumerate(args) if i not in fds]] if fds else [])
    if not any(strip_flags(v, flags, with_value) == want for v in variants):
        return False, "the arguments differ"
    for name, value in sorted((actual_env or {}).items()):
        if (env or {}).get(name) != value:
            return False, "the inline variable {}={} is not declared in `env`".format(name, value)
    return True, ""
