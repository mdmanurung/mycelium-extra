"""Plan-table reading for the plan-approval gate: the cells that grant runs, the paths and commands they
name, the plan's rows and the scripts it covers.

hooks/gate.py imports every name here and re-exports it, so `gate.plan_table` and the rest keep working.
Stdlib-only and cheap to import: the hooks load it on every call.
"""

import functools
import os
import re

from shellwords import SCRIPT_EXT, PATHLIKE, gated_rel, repo_relative


TABLE_ROW = re.compile(r"^\s*\|(.*)\|\s*$")
TABLE_RULE = re.compile(r"^\s*\|?[\s|:]*-[\s|:-]*$")
SOURCE_CITATION = re.compile(r"`?\brepo:\s*`?[^\s`|;,]+`?")
MAX_SCRIPT_PINS = 500


@functools.lru_cache(maxsize=None)
def plan_table(plan, every_cell=False):
    """The text of the cells that grant runs: under a header with a Step column, the Step cells
    only; otherwise every cell but Source. `repo:` citations are dropped.

    Only the table approves runs: a path or command word in prose, Evidence, a Choice or
    Validation cell, or a source citation approves nothing. `every_cell` keeps every cell but
    Source, as before 0.9.57, for verify's record of what a plan named. "" with no table.
    """
    lines = plan.splitlines()
    cells, keep = [], None  # keep: a test for the column index of a cell that counts
    for i, line in enumerate(lines):
        if not TABLE_ROW.match(line):
            keep = None
            continue
        if TABLE_RULE.match(line):
            continue
        parts = [cell.replace("\0", "|").strip()
                 for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if TABLE_ROW.match(following) and TABLE_RULE.match(following):  # a header row
            heads = [cell.lower() for cell in parts]
            step = set([j for j, cell in enumerate(heads) if "step" in cell][:1])  # as plan_rows reads it
            source = set(j for j, cell in enumerate(heads) if "source" in cell)
            keep = (lambda j, step=step: j in step) if step and not every_cell else (
                lambda j, source=source: j not in source)
            continue
        cells += [cell for j, cell in enumerate(parts) if keep is None or keep(j)]
    return SOURCE_CITATION.sub(" ", "\n".join(cells))


def names_command(command, table):
    return re.search(r"\b{}\b".format(re.escape(command)), table) is not None


@functools.lru_cache(maxsize=None)
def plan_paths(table):
    tokens = set()
    for word in PATHLIKE.findall(table):
        word = word.rstrip(".,;:").rstrip("/")
        if word.startswith("./"):
            word = word[2:]
        if "/" in word:
            tokens.add(word)
    return frozenset(tokens)  # cached, so callers must not mutate it


def plan_paths_in(root, table):
    """plan_paths with each path inside the project root made root-relative, the one form the
    gate and verify compare; a path outside the root stays as written."""
    literals = []

    def quoted(match):
        path = match.group(2)
        if any(c.isspace() for c in path) and os.path.exists(os.path.join(root, os.path.expanduser(path))):
            literals.append(path)
            return ""  # Its fragments must not accidentally grant a parent folder.
        return match.group(0)

    table = re.sub(r"([`\"'])([^`\"'\n]+)\1", quoted, table)
    return frozenset((repo_relative(root, root, p) or p) if os.path.isabs(p) else p
                     for p in list(plan_paths(table)) + literals)


def path_in_plan(root, path, table):
    named = plan_paths_in(root, table)
    parts = path.split("/")
    return any("/".join(parts[:depth]) in named for depth in range(len(parts), 1, -1))


def plan_grants(root, plan, config):
    """(gated paths, gated commands) the plan table lets through: a path covers itself and
    everything gated below it, a command covers every invocation."""
    table = plan_table(plan)
    paths = sorted(set(gated_rel(root, root, p, config) for p in plan_paths_in(root, table)) - set([None]))
    return paths, [c for c in config["gated_commands"] if names_command(c, table)]


def table_cells(line):
    return [cell.replace("\0", "|").strip() for cell in TABLE_ROW.match(line).group(1).replace("\\|", "\0").split("|")]


def plan_rows(text):
    """The first plan table with a Step column and a Choice or Validation column, as a list of
    {num, step, choice, source, check, id, cells, head}; None when there is no such table. `id` is
    the cell of a `#`, `no`, `no.` or `ID` column (None without one; `num` then counts the rows);
    `cells` and `head` are every cell of the row and of the header, for comparing plans."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        following = lines[i + 1] if i + 1 < len(lines) else ""
        if not TABLE_ROW.match(line) or TABLE_RULE.match(line) or not (
                TABLE_ROW.match(following) and TABLE_RULE.match(following)):
            continue
        column, head = {}, tuple(table_cells(line))
        for j, cell in enumerate(c.lower() for c in head):
            for key, words in (("step", ("step",)), ("choice", ("choice",)), ("source", ("source",)),
                               ("check", ("validation", "check"))):
                if key not in column and any(word in cell for word in words):
                    column[key] = j
            if cell in ("#", "no", "no.", "id") and "num" not in column:
                column["num"] = j
        if "step" not in column or not ("choice" in column or "check" in column):
            continue
        rows = []
        for row in lines[i + 2:]:
            if not TABLE_ROW.match(row):
                break
            if TABLE_RULE.match(row):
                continue
            cells = table_cells(row)
            cell = lambda key: cells[column[key]] if key in column and column[key] < len(cells) else ""
            rows.append({"num": cell("num") or str(len(rows) + 1), "step": cell("step"),
                         "choice": cell("choice"), "source": cell("source"), "check": cell("check"),
                         "id": cell("num") if "num" in column else None, "cells": tuple(cells), "head": head})
        return rows
    return None


def covered_scripts(root, text, config):
    """Existing script files the plan table names. A script under a folder it names, or
    one that does not exist yet, is pinned at its first run instead."""
    found = []
    for named in sorted(plan_paths_in(root, plan_table(text))):
        rel = gated_rel(root, root, named, config)
        if rel and SCRIPT_EXT.search(rel) and os.path.isfile(os.path.join(root, rel)):
            found.append(rel)
    return sorted(set(found))[:MAX_SCRIPT_PINS]
