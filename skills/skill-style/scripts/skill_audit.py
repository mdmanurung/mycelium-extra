#!/usr/bin/env python3
"""Read-only style audit of a plugin's skills (advisory; exit 0 always).

Run: sh <skill-dir>/../../hooks/py.sh - [--root DIR] [--format table|json|both] < <this file>
Reads <root>/skills/*/SKILL.md and each skill's references/ folder. Writes nothing.
Exit 0 always, 2 when the root or its skills folder is unusable.
"""
import json
import re
import sys
from pathlib import Path

MAX_WORDS = 60
MAX_FIRST_SENTENCE = 150
SPRAWL_LINES = 150
WEAK_LEADS = {"this", "a", "an", "the", "it", "these", "those"}
NEGATION = re.compile(r"\b(never|don't|don’t|do not|must not)\b", re.I)
CRITERION = re.compile(
    r"done when|\buntil\b|only when|\bverif|\bconfirm|\bstop\b|\bwait\b|\bexits? \d|\bmatch(es)?\b|\bexists?\b"
    r"|\bno \w+ (remain|left)|\bevery\b.*\b(listed|named|checked|accounted)",
    re.I,
)
# A numbered list under one of these headings is a format or a set of kinds, not a sequence of steps.
NOT_STEPS = re.compile(r"format|types?\b|kinds?\b|options|families|rules|columns|fields|parts|what you get", re.I)
DUP_MIN_WORDS = 8


def usage_error(message):
    print("skill_audit: " + message, file=sys.stderr)
    sys.exit(2)


def parse_args(argv):
    root, fmt = Path("."), "both"
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--root" and args:
            root = Path(args.pop(0))
        elif arg == "--format" and args:
            fmt = args.pop(0)
        else:
            usage_error("usage: [--root DIR] [--format table|json|both]; got " + arg)
    if fmt not in ("table", "json", "both"):
        usage_error("--format takes table, json or both")
    return root, fmt


def split_frontmatter(text):
    parts = text.split("---", 2)
    if text.startswith("---") and len(parts) == 3:
        return parts[1], parts[2]
    return "", text


def read_frontmatter(block):
    fields = {}
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            value = m.group(2).strip()
            if value not in ("|", ">", "|-", ">-"):
                # a plain or quoted scalar may continue on indented lines
                for more in lines[i + 1:]:
                    if more[:1] in (" ", "\t") and more.strip():
                        value += " " + more.strip()
                    else:
                        break
            fields[m.group(1)] = value
    desc = fields.get("description", "")
    block_scalar = desc in ("|", ">", "|-", ">-")
    if len(desc) >= 2 and desc[0] == desc[-1] and desc[0] in "\"'":
        desc = desc[1:-1]
    return fields, desc, block_scalar


def strip_code(body):
    out, fenced = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def steps_of(lines):
    """Numbered steps as (label, text): numbered headings with their section, else numbered list items.
    A list item carries its whole section, so a section-level 'Done when' counts for every item.
    A list under a heading such as 'Format' or 'Types' is a set of kinds, not steps, and is skipped."""
    heads = [i for i, ln in enumerate(lines) if re.match(r"^#{2,4}\s+\d+[.)]", ln)]
    if len(heads) >= 2:
        bounds = heads + [next((i for i in range(heads[-1] + 1, len(lines)) if re.match(r"^#{1,4}\s", lines[i])), len(lines))]
        return [(lines[a].strip("# ").strip()[:40], "\n".join(lines[a:b])) for a, b in zip(bounds, bounds[1:])]
    items = [i for i, ln in enumerate(lines) if re.match(r"^\d+[.)]\s", ln)]
    if len(items) < 2:
        return []
    steps = []
    for n, a in enumerate(items):
        top = max((j for j in range(a) if re.match(r"^#{1,4}\s", lines[j])), default=0)
        if NOT_STEPS.search(lines[top]) and re.match(r"^#{1,4}\s", lines[top]):
            continue
        level = len(re.match(r"^#*", lines[top]).group())
        end = next((j for j in range(a + 1, len(lines))
                    if re.match(r"^#{1,4}\s", lines[j]) and len(re.match(r"^#*", lines[j]).group()) <= max(level, 1)), len(lines))
        item_end = items[n + 1] if n + 1 < len(items) else end
        steps.append((lines[a][:40], "\n".join(lines[a:item_end]) + "\n" + "\n".join(lines[top:end])))
    return steps


def reference_files(skill_dir):
    ref = skill_dir / "references"
    if not ref.is_dir():
        return []
    return sorted(p for p in ref.rglob("*") if p.is_file())


def named_in(text, name):
    """True when text holds name as a whole path or file name, not inside a longer one."""
    return bool(re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])", text))


def mentions(text, path, skill_dir):
    rel = path.relative_to(skill_dir).as_posix()
    if named_in(text, rel) or named_in(text, path.name):
        return True
    # a pointer to a folder covers the files under it
    return any(named_in(text, parent.relative_to(skill_dir).as_posix())
               for parent in path.parents if parent != skill_dir and skill_dir in parent.parents and parent.name != "references")


def read_tree(skill_dir, names):
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for name in names for p in sorted((skill_dir / name).rglob("*"))
                     if p.is_file() and p.suffix in (".md", ".txt", ".yaml", ".yml", ".py", ".sh"))


def orphans_of(skill_dir, skill_text, other_skills_text="", tests_text=""):
    """Return (orphans, developer_only). A reference is reached from the skill's own pointers, or from
    another skill by its skill-folder path. One that only a test names is developer-only, not an orphan."""
    files = reference_files(skill_dir)
    reached, frontier = set(), [skill_text]
    while frontier:
        text = frontier.pop()
        for path in files:
            if path not in reached and mentions(text, path, skill_dir):
                reached.add(path)
                if path.suffix in (".md", ".txt", ".yaml", ".yml"):
                    frontier.append(path.read_text(encoding="utf-8", errors="replace"))
    for path in files:
        if path not in reached and named_in(other_skills_text, skill_dir.name + "/" + path.relative_to(skill_dir).as_posix()):
            reached.add(path)
    developer = [p for p in files if p not in reached and mentions(tests_text, p, skill_dir)]
    rel = lambda ps: [p.relative_to(skill_dir).as_posix() for p in ps]
    return rel([p for p in files if p not in reached and p not in developer]), rel(developer)


def sentences_of(lines):
    found = []
    for line in lines:
        line = re.sub(r"^\s*(?:[-*>]|\d+[.)])\s+", "", line)
        for cell in line.split("|"):
            for piece in re.split(r"(?<=[.!?:;])\s+", cell):
                words = re.sub(r"[`*_#\[\]()]", "", piece).lower().split()
                if len(words) >= DUP_MIN_WORDS:
                    found.append(" ".join(words).rstrip(".!?:;"))
    return found


def audit_skill(skill_dir, other_text=""):
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    block, body = split_frontmatter(text)
    fields, desc, block_scalar = read_frontmatter(block)
    lines = strip_code(body)
    all_lines = body.splitlines()
    words = desc.split()
    first = desc.split(". ")[0]
    first_word = words[0].lower().strip(":,") if words else ""
    orphans, developer = orphans_of(skill_dir, text, other_text, read_tree(skill_dir, ["tests"]))
    negations = len(NEGATION.findall("\n".join(all_lines)))
    review = [label for label, step in steps_of(lines) if not CRITERION.search(step)]
    return {
        "skill": skill_dir.name,
        "invocation": "user" if fields.get("disable-model-invocation", "").lower() == "true" else "model",
        "desc_words": len(words),
        "first_sentence_chars": len(first),
        "over_cap": len(words) > MAX_WORDS or len(first) > MAX_FIRST_SENTENCE or block_scalar or not desc,
        "first_word": first_word,
        "leading_word_ok": bool(first_word) and first_word not in WEAK_LEADS,
        "lines": len(text.splitlines()),
        "sprawl": len(text.splitlines()) > SPRAWL_LINES,
        "negations": negations,
        "negations_per_100_lines": round(100 * negations / max(len(all_lines), 1), 1),
        "steps_to_review": review,
        "orphan_references": orphans,
        "developer_references": developer,
    }


def duplicate_sentences(skill_dirs):
    seen = {}
    for skill_dir in skill_dirs:
        files = [skill_dir / "SKILL.md"] + [p for p in reference_files(skill_dir) if p.suffix == ".md"]
        for path in files:
            body = split_frontmatter(path.read_text(encoding="utf-8", errors="replace"))[1]
            for sentence in set(sentences_of(strip_code(body))):
                seen.setdefault(sentence, set()).add(path.relative_to(skill_dir.parent).as_posix())
    dups = [{"sentence": s, "files": sorted(f)} for s, f in seen.items() if len(f) >= 2]
    return sorted(dups, key=lambda d: (-len(d["files"]), d["sentence"]))


def render_table(report):
    head = ["skill", "inv", "desc_w", "1st_chars", "lead", "lines", "sprawl", "neg/100", "steps?", "orphans"]
    rows = [head]
    for s in report["skills"]:
        rows.append([
            s["skill"], s["invocation"][0].upper(), str(s["desc_words"]) + ("!" if s["over_cap"] else ""),
            str(s["first_sentence_chars"]), s["first_word"] if not s["leading_word_ok"] else "ok",
            str(s["lines"]), "SPRAWL" if s["sprawl"] else "-", str(s["negations_per_100_lines"]),
            str(len(s["steps_to_review"])), str(len(s["orphan_references"])),
        ])
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    out = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    t = report["totals"]
    out += ["", f"skills: {t['skills']}  model-invoked: {t['model_invoked']}  always-loaded description words: {t['model_invoked_description_words']}",
            f"over cap: {t['over_cap']}  weak leading word: {t['weak_leading_word']}  sprawl: {t['sprawl']}  "
            f"orphan references: {t['orphan_references']}  steps to review: {t['steps_to_review']}  duplicate sentences: {t['duplicate_sentences']}"]
    if report["duplicate_sentences"]:
        out += ["", "duplicate sentences (first 10):"]
        out += [f"  [{len(d['files'])} files] {d['sentence'][:90]}" for d in report["duplicate_sentences"][:10]]
    out += ["", "M = model-invoked (description always loaded), U = user-invoked. '!' = over the description cap. steps? = numbered steps with no completion cue in the step or its section (review, a heuristic). orphans = references/ files no SKILL.md, reference or other skill points at; files only a test names are listed as developer_references in the JSON."]
    return "\n".join(out)


def main():
    root, fmt = parse_args(sys.argv[1:])
    skills_root = root / "skills" if (root / "skills").is_dir() else root
    if not skills_root.is_dir():
        usage_error("not a directory: " + str(root))
    skill_dirs = sorted(p.parent for p in skills_root.glob("*/SKILL.md"))
    if not skill_dirs:
        usage_error("no skills/*/SKILL.md under " + str(root))
    texts = {d: (d / "SKILL.md").read_text(encoding="utf-8", errors="replace") + "\n" + read_tree(d, ["references"])
             for d in skill_dirs}
    skills = [audit_skill(d, "\n".join(v for k, v in texts.items() if k != d)) for d in skill_dirs]
    dups = duplicate_sentences(skill_dirs)
    model = [s for s in skills if s["invocation"] == "model"]
    report = {
        "root": str(root),
        "skills": skills,
        "duplicate_sentences": dups,
        "totals": {
            "skills": len(skills),
            "model_invoked": len(model),
            "model_invoked_description_words": sum(s["desc_words"] for s in model),
            "over_cap": sum(s["over_cap"] for s in skills),
            "weak_leading_word": sum(not s["leading_word_ok"] for s in skills),
            "sprawl": sum(s["sprawl"] for s in skills),
            "orphan_references": sum(len(s["orphan_references"]) for s in skills),
            "steps_to_review": sum(len(s["steps_to_review"]) for s in skills),
            "duplicate_sentences": len(dups),
        },
    }
    if fmt in ("table", "both"):
        print(render_table(report))
    if fmt == "both":
        print("\nJSON:")
    if fmt in ("json", "both"):
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
