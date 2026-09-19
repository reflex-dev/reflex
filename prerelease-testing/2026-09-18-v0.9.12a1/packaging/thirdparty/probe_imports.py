import sys, re, glob
import reflex
print("reflex", reflex.constants.Reflex.VERSION, reflex.__file__)
lines=set()
for f in glob.glob("src/**/*.py", recursive=True):
    src=open(f, encoding="utf-8", errors="ignore").read()
    for m in re.finditer(r"^\s*(from reflex[\w.]* import \(?[^)\n]*\)?|import reflex[\w.]*(?: as \w+)?)", src, re.M):
        lines.add(re.sub(r"[()]", "", m.group(1)).strip())
bad=0
for l in sorted(lines):
    try: exec(l, {})
    except Exception as e:
        bad+=1; print("FAIL:", l, "->", type(e).__name__, str(e)[:160])
print("checked", len(lines), "import lines; failures:", bad)
