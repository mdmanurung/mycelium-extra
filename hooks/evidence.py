"""Portable, allowlisted projection of an already computed verification result."""
import hashlib
import json
import re
import time

SCHEMA = "mycelium-extra.evidence-handoff.v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def relative(value):
    return (isinstance(value, str) and bool(value) and not value.startswith(("/", "\\"))
            and not re.search(r"[:\\\x00-\x1f]", value) and ".." not in value.split("/"))


def identity(value):
    return digest({k: v for k, v in value.items() if k not in
                   ("generated_at", "snapshot_digest", "producer", "references")})


def project(result, version="unknown", generated_at=None, references=None):
    """No verification, markdown parsing, environment export or implicit publication."""
    withheld = set()
    sensitive = []
    for receipt in result.get("receipts") or []:
        command = receipt.get("command")
        if isinstance(command, str) and command:
            sensitive += [command, command[:120], command[:80], command[:60]]
        for key in ("command_env", "hook_env"):
            sensitive += list((receipt.get(key) or {}).values())

    def text(value):
        if not isinstance(value, str):
            return value
        old = value
        for secret in sensitive:
            if isinstance(secret, str) and secret:
                value = value.replace(secret, "[withheld]")
        # Findings about other instances may quote commands absent from selected receipts.
        value = re.sub(r"`([^`]*)`", lambda m: "`[withheld command/arguments]`" if (
            (any(c.isspace() for c in m[1]) and m[1] not in ("Outputs: none", "Plan status: READY"))
            or re.match(r"^(?:python[0-9.]*|Rscript|bash|sh|sbatch|srun|snakemake|nextflow|env|conda)(?:\s|$)", m[1])) else m[0], value)
        value = re.sub(r"(?<![\w.])/(?:[^\s`'\";,]+)", "[withheld path]", value)
        value = re.sub(r"(?i)\b(?:token|password|secret|api_key)\s*[:=]\s*\S+", "[withheld]", value)
        if value != old:
            withheld.add("text containing commands, environment values or absolute paths")
        return value

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [clean(v) for v in value]
        return text(value)

    def path(value):
        if relative(value):
            return value if text(value) == value else None
        if value is not None:
            withheld.add("non-relative paths")
        return None

    outputs = []
    for row in result.get("outputs") or []:
        record = row.get("record") or {}
        outputs.append({"path": path(row.get("path")),
                        "fingerprint": {k: record[k] for k in ("sha256", "size", "mtime", "method", "missing", "folder", "skipped") if k in record},
                        "fingerprint_method": ("sha256" if record.get("sha256") else
                                               "missing" if record.get("missing") else
                                               "folder listing" if record.get("folder") else
                                               "not pinned: " + record["skipped"] if record.get("skipped") else
                                               "size+mtime" if record else None),
                        "producer_attempt": row.get("producer_attempt"),
                        "evidence_method": row.get("evidence_method"), "strength": row.get("strength"),
                        "explore": row.get("explore")})
    q = result.get("qualification")
    qualification = None if q is None else clean({
        "overall": q.get("overall"), "limitation": q.get("limitation"),
        "dimensions": [{k: row[k] for k in ("dimension", "state", "reason") if k in row}
                       for row in q.get("dimensions") or []]})
    scope = result.get("scope") or {}
    coverage = {k: scope[k] for k in ("runs", "outputs", "supported", "candidate", "unresolved") if k in scope}
    coverage["launch"] = {k: scope.get("launch", {}).get(k) for k in ("matched", "unmatched", "ambiguous", "legacy")}
    observation = scope.get("observation") or {}
    coverage["observation"] = {k: observation[k] for k in ("gate_errors", "open_attempts", "off_contract") if k in observation}
    coverage["observation"]["steps"] = [
        {"step": "[withheld step label; see original report]", "complete": row.get("complete"), "why": text(row.get("why"))}
        for row in observation.get("steps") or []]
    if observation.get("steps"):
        withheld.add("step labels may contain command arguments")
    value = {"schema": SCHEMA, "producer": {"name": "mycelium-extra", "version": version},
             "generated_at": generated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "analysis_path": path(result.get("analysis_dir")), "plan_hash": result["hash"],
             "approval_instance": (result.get("instance") or {}).get("selected"),
             "conformity": result.get("status"), "qualification": qualification,
             "outputs": outputs, "findings": clean(result.get("findings") or []),
             "coverage": clean(coverage),
             "limitations": ["Evidence linkage is not scientific validity.",
                              "Missing SHA256 is not content identity; size/mtime is weak."],
             "references": {k: path(v) for k, v in (references or {}).items()},
             "withheld": sorted(withheld | {"transcripts", "commands and arguments", "environment values", "raw data"})}
    value = clean(value)
    value["withheld"] = sorted(set(value["withheld"]) | withheld)
    value["snapshot_digest"] = identity(value)
    return value
