"""Extract and urldecode the `data:text/javascript` dynamic-component modules a
Reflex server log echoes back inside [Reflex Frontend Exception] blocks."""

import re
import sys
from urllib.parse import unquote

raw = open(sys.argv[1]).read()
# The log hard-wraps the data URI; rejoin by stripping newlines inside each URI.
joined = re.sub(r"\n(?=[%A-Za-z0-9_.+*/'()-])", "", raw)
seen = set()
for m in re.finditer(r"data:text/javascript;charset=utf-8,([^\s]+)", joined):
    code = unquote(m.group(1))
    head = "\n".join(
        line for line in code.splitlines() if line.startswith(("import ", "const "))
    )
    if head in seen:
        continue
    seen.add(head)
    print(f"--- distinct module #{len(seen)} ---")
    print(head)
    print()
