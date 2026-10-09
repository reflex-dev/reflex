"""Lift the body of AuthFlowApp() out of reflex-enterprise's tests/integration/test_auth_flow.py into a module-scope app.

Usage: python -I lift_app.py <test_auth_flow.py> <out auth.py>
(The 10-05 matrix ran this lifted copy; it is generated at run time so no enterprise source lives in the repo.)
"""

import ast
import sys
import textwrap
from pathlib import Path

src_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
src = src_path.read_text()
for node in ast.parse(src).body:
    if isinstance(node, ast.FunctionDef) and node.name == "AuthFlowApp":
        body = node.body[1:] if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) else node.body
        lines = src.splitlines()[body[0].lineno - 1 : node.end_lineno]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text('"""Upstream AuthFlowApp, lifted to module scope for CLI execution."""\n\n' + textwrap.dedent("\n".join(lines)) + "\n")
        print(f"lifted AuthFlowApp ({len(lines)} lines) -> {out_path}")
        break
else:
    sys.exit(f"AuthFlowApp not found in {src_path}")
