"""Heuristic: state-class attributes whose default is a bare module-level NAME that the same module mutates
(append/extend/update/insert/add/setdefault/[k]=, or `global NAME` reassign) anywhere. Usage: python3 grep_late.py <dir>..."""
import ast
import pathlib
import sys

MUT = {"append", "extend", "update", "insert", "add", "setdefault", "clear", "pop", "remove"}
hits = []
for root in sys.argv[1:]:
    for p in pathlib.Path(root).rglob("*.py"):
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        mutated = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUT and isinstance(n.func.value, ast.Name):
                mutated.add(n.func.value.id)
            if isinstance(n, (ast.Assign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        mutated.add(t.value.id)
        for c in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            bases = " ".join(ast.unparse(b) for b in c.bases)
            if "State" not in bases:
                continue
            for st in c.body:
                v = st.value if isinstance(st, (ast.Assign, ast.AnnAssign)) else None
                if isinstance(v, ast.Name) and v.id in mutated:
                    hits.append(f"{p}:{st.lineno}: {c.name}: {ast.unparse(st)[:120]}  (module mutates {v.id})")
                elif isinstance(v, ast.Name):
                    hits.append(f"(name default, not mutated) {p}:{st.lineno}: {c.name}: {ast.unparse(st)[:100]}")
print("\n".join(hits) or "no hits")
