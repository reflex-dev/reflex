"""Statically resolve every `from <reflex pkg> import name` (incl. function-level imports) in this venv.

Reports imported names that don't exist in the installed target module, i.e. cross-package API drift
between the installed versions of reflex, reflex_base and the component packages.
"""
import ast
import importlib
import pathlib
import sys

import reflex

EXPECT = sys.argv[1]
assert EXPECT in reflex.__file__, reflex.__file__
site = pathlib.Path(reflex.__file__).parent.parent
PKGS = sorted(p.name for p in site.iterdir() if p.is_dir() and p.name.startswith("reflex") and not p.name.endswith((".dist-info",)))
print("packages:", PKGS)
problems = []
checked = 0
for pkg in PKGS:
    for f in (site / pkg).rglob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            problems.append((str(f), f"SyntaxError {e}"))
            continue
        modname = ".".join(f.relative_to(site).with_suffix("").parts)
        if modname.endswith(".__init__"):
            modname = modname[: -len(".__init__")]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                target = node.module
                top = target.split(".")[0]
                if not top.startswith("reflex"):
                    continue
                # only cross-package references
                if top == pkg:
                    continue
                try:
                    m = importlib.import_module(target)
                except Exception as e:  # noqa: BLE001
                    problems.append((f"{modname}:{node.lineno}", f"import {target} -> {type(e).__name__}: {e}"))
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    checked += 1
                    if not hasattr(m, alias.name):
                        try:
                            importlib.import_module(f"{target}.{alias.name}")
                        except Exception:  # noqa: BLE001
                            problems.append((f"{modname}:{node.lineno}", f"from {target} import {alias.name} -> MISSING"))
print(f"checked {checked} cross-package imported names")
for where, what in problems:
    print("PROBLEM", where, what)
