"""Static scan: which State members declared by downstream code collide with #7136's reserved names?"""
import ast, sys, glob, os
import reflex as rx
assert "/envs/shared/" in rx.__file__, rx.__file__
from reflex.istate.validation import _reserved_state_members
reserved = _reserved_state_members()
print(f"reserved members on 0.9.12a1: {len(reserved)}")
print("sample:", sorted(reserved)[:60])
STATE_BASES = {"State", "rx.State", "ComponentState", "rx.ComponentState", "BaseState", "AuthUserState", "rxe.State"}
def base_name(b):
    return ast.unparse(b) if hasattr(ast, "unparse") else ""
hits = []
for root in sys.argv[1:]:
    for f in glob.glob(root + "/**/*.py", recursive=True):
        if "/.web/" in f or "/node_modules/" in f or "/tests/" in f: continue
        try: tree = ast.parse(open(f, encoding="utf-8", errors="ignore").read())
        except SyntaxError: continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef): continue
            bases = {base_name(b) for b in node.bases}
            if not (bases & STATE_BASES) and not any(b.endswith("State") for b in bases): continue
            for item in node.body:
                names = []
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name): names = [item.target.id]
                elif isinstance(item, ast.Assign): names = [t.id for t in item.targets if isinstance(t, ast.Name)]
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)): names = [item.name]
                for n in names:
                    if n in reserved and not n.startswith("__"):
                        kind = type(item).__name__
                        hits.append((f.replace(os.path.dirname(root)+"/", ""), node.name, n, kind, item.lineno))
for h in sorted(hits): print("HIT", *h)
print("total hits:", len(hits))
