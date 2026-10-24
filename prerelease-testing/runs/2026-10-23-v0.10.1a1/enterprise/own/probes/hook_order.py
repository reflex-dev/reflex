"""Static check of compiled page modules for hooks that reference identifiers declared LATER in the same component
(a TDZ ReferenceError at render) -- the #7586 hazard for rxe's dnd (useDrag/useDrop, POST_TRIGGER) and mantine
combobox (useCombobox, PRE_TRIGGER) hooks.

Usage: hook_order.py <.web dir> <label> [page glob substrings...]
Prints, per page module and per function body, the line of each interesting hook call, the identifiers it references
that are declared in the same function, and which of those are declared after the hook ('use-before-declare').
"""
import json
import re
import sys
from pathlib import Path

web = Path(sys.argv[1])
label = sys.argv[2]
subs = sys.argv[3:] or ["dnd", "basic", "foreach", "kanban", "combobox", "index"]
HOOKS = re.compile(r"\b(use[A-Z]\w*)\s*\(")  # every hook call; late refs are what matter
DECL = re.compile(r"^\s*(?:const|let|var)\s+(?:\[\s*)?([A-Za-z_$][\w$]*)")
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
files = []
for pat in ("app/routes/**/*.jsx", "app/routes/**/*.js", "app/**/*.jsx", "utils/**/*.js", "components/**/*.jsx"):
    for f in web.glob(pat):
        if any(s in str(f.relative_to(web)) for s in subs) or any(s in f.read_text(errors="replace")[:200000] for s in ("useDrop(", "useDrag(", "useCombobox(")):
            files.append(f)
files = sorted(set(files))
report = {}
for f in files:
    text = f.read_text(errors="replace")
    if not HOOKS.search(text):
        continue
    lines = text.split("\n")
    # split into function bodies by 'function NAME(' / 'export function' / 'const NAME = (' lines at col 0-2
    starts = [i for i, ln in enumerate(lines) if re.match(r"^(export\s+)?(default\s+)?function\s+\w+|^(export\s+)?const\s+\w+\s*=\s*(memo\()?\(|^const\s+\w+\s*=\s*memo\(", ln)]
    starts.append(len(lines))
    out = []
    for a, b in zip(starts, starts[1:]):
        body = lines[a:b]
        decls = {}
        for i, ln in enumerate(body):
            m = DECL.match(ln)
            if m:
                decls.setdefault(m.group(1), i)
                for extra in re.findall(r"\[\s*([^\]]+)\]\s*=", ln):
                    for nm in IDENT.findall(extra):
                        decls.setdefault(nm, i)
        for i, ln in enumerate(body):
            hm = HOOKS.search(ln)
            if not hm:
                continue
            # the hook call may span lines: take until the statement ends (a line ending with ';' at the same nesting)
            j = i
            depth = 0
            chunk = []
            while j < len(body):
                chunk.append(body[j])
                depth += body[j].count("(") - body[j].count(")")
                if depth <= 0 and body[j].rstrip().endswith((";", ")")):
                    break
                j += 1
            stmt = "\n".join(chunk)
            refs = sorted({nm for nm in IDENT.findall(stmt) if nm in decls and decls[nm] != i and not nm.startswith("use")})
            late = [nm for nm in refs if decls[nm] > j]
            out.append({"fn_line": a + 1, "hook": hm.group(1), "line": a + i + 1, "refs": refs, "use_before_declare": late,
                        "ref_lines": {nm: a + decls[nm] + 1 for nm in refs}})
    if out:
        report[str(f.relative_to(web))] = out
bad = {k: [h for h in v if h["use_before_declare"]] for k, v in report.items()}
bad = {k: v for k, v in bad.items() if v}
for k, v in report.items():
    for h in v:
        flag = "USE-BEFORE-DECLARE" if h["use_before_declare"] else "ok"
        if h["use_before_declare"] or h["hook"] in ("useDrag", "useDrop", "useDragLayer", "useCombobox"):
            print(f"{flag:19} {k}:{h['line']} {h['hook']} refs={h['refs']} late={h['use_before_declare']}")
print(f"SUMMARY {label} hook_order: {sum(len(v) for v in report.values())} hook calls in {len(report)} files; use-before-declare in {len(bad)} files")
json.dump({"label": label, "report": report, "bad": bad}, open(Path(__file__).resolve().parent.parent / "out" / f"hook_order_{label}.json", "w"), indent=1)
