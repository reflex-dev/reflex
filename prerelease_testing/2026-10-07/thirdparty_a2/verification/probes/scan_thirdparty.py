"""Scan installed third-party reflex packages for class-level assignment to State attributes.

Independent verifier probe. Looks (AST + regex) for patterns that #7461's BaseStateMeta.__setattr__ now intercepts:
  * ``<StateClass>.attr = value``  (module level, functions, methods)
  * ``cls.attr = value`` / ``setattr(cls, ...)`` / ``setattr(<StateClass>, ...)`` inside State / ComponentState classes
  * ``delattr(<StateClass>, ...)``
  * ``__fields__[...].default = ...`` (the pre-#7461 documented ComponentState way; still fine)
  * ``monkeypatch.setattr(<StateClass>, ...)`` / ``mock.patch.object(<StateClass>, ...)`` (tests shipped in wheels)

Run with the venv python:  <venv>/bin/python -I scan_thirdparty.py <site-packages dir> <dist name>...
"""

import ast
import os
import re
import sys
from importlib import metadata

SITE = sys.argv[1]
DISTS = sys.argv[2:]

STATE_BASE_HINTS = {"State", "ComponentState", "BaseState", "SharedState", "MixinState", "AppState"}
CLASS_ATTR_ASSIGN_RE = re.compile(r"^\s*(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\.(?P<attr>[A-Za-z_][A-Za-z0-9_]*)\s*=[^=]")
PATCH_RE = re.compile(r"(monkeypatch\.(setattr|delattr)|mock\.patch(\.object)?|patch\.object|mocker\.patch)")
FIELDS_DEFAULT_RE = re.compile(r"__fields__\[.+?\]\.default\s*=")


def py_files(dist_name):
    try:
        files = metadata.files(dist_name) or []
    except metadata.PackageNotFoundError:
        return []
    out = []
    for f in files:
        s = str(f)
        if s.endswith(".py") and ".dist-info" not in s and not s.startswith(".."):
            p = os.path.join(SITE, s)
            if os.path.isfile(p):
                out.append((s, p))
    return out


def base_names(cls: ast.ClassDef):
    names = []
    for b in cls.bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            names.append(b.attr)
    return names


def state_like_classes(tree):
    """Fixed point: classes whose bases look like State bases or other state-like classes in the module."""
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    like = set()
    changed = True
    while changed:
        changed = False
        for c in classes:
            if c.name in like:
                continue
            bn = base_names(c)
            if any(b in STATE_BASE_HINTS or b in like or b.endswith("State") for b in bn):
                like.add(c.name)
                changed = True
    return like, {c.name: c for c in classes}


def target_root(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def scan_file(rel, path):
    findings = []
    try:
        src = open(path, encoding="utf-8").read()
    except Exception:  # noqa: BLE001
        return findings
    lines = src.splitlines()
    # regex-level (catches anything the AST pass misses, including tests)
    for i, line in enumerate(lines, 1):
        if FIELDS_DEFAULT_RE.search(line):
            findings.append(("fields-default", rel, i, line.strip()))
        if PATCH_RE.search(line) and "State" in line:
            findings.append(("patch-on-state?", rel, i, line.strip()))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return findings
    like, classes = state_like_classes(tree)
    # map: function node -> enclosing class (for cls.attr inside classmethods of state-like classes)
    parent_class = {}
    for c in classes.values():
        for n in ast.walk(c):
            parent_class.setdefault(id(n), c)
    for node in ast.walk(tree):
        # attribute assignment statements
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute):
                    root = target_root(t)
                    if root in like:
                        findings.append(("StateClass.attr=", rel, node.lineno, lines[node.lineno - 1].strip()))
                    elif root == "cls":
                        enc = parent_class.get(id(node))
                        if enc is not None and enc.name in like:
                            findings.append(("cls.attr= in state class", rel, node.lineno, lines[node.lineno - 1].strip()))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"setattr", "delattr"} and node.args:
            first = node.args[0]
            root = target_root(first) if isinstance(first, (ast.Name, ast.Attribute)) else None
            if root in like:
                findings.append((f"{node.func.id}(StateClass,..)", rel, node.lineno, lines[node.lineno - 1].strip()))
            elif root == "cls":
                enc = parent_class.get(id(node))
                if enc is not None and enc.name in like:
                    findings.append((f"{node.func.id}(cls,..) in state class", rel, node.lineno, lines[node.lineno - 1].strip()))
    return findings


def main():
    total_files = 0
    allf = []
    for d in DISTS:
        fl = py_files(d)
        total_files += len(fl)
        hits = []
        for rel, p in fl:
            hits += scan_file(rel, p)
        allf.append((d, len(fl), hits))
    print(f"scanned {len(DISTS)} distributions, {total_files} .py files under {SITE}")
    for d, n, hits in allf:
        print(f"\n## {d}  ({n} .py files)  hits={len(hits)}")
        for kind, rel, ln, txt in hits:
            print(f"   [{kind}] {rel}:{ln}: {txt[:150]}")


if __name__ == "__main__":
    main()
