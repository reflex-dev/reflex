"""Copy prerelease-testing/fixtures/enterprise to a work copy with ports remapped into the enterprise cluster range."""
import re, shutil, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", ".web"))
common = {"3620": "3390", "3622": "3392", "3623": "3393", "3624": "3394",
          "8620": "8390", "8621": "8391", "8622": "8392", "8623": "8393", "8624": "8394",
          "8625": "8395", "8626": "8396", "8629": "8399", "8638": "8398", "8639": "8397"}
grid = {f"36{i:02d}": f"33{80+i}" for i in range(20)} | {f"86{i:02d}": f"83{80+i}" for i in range(20)}
literal = [("3620-3639", "3390-3399"), ("8620-8628", "8390-8396"), ("8630-8637", "8390-8396"),
           ("36[01][0-9]|86[01][0-9]", "33[89][0-9]|83[89][0-9]")]
n = 0
for p in dst.rglob("*"):
    if p.suffix not in {".sh", ".py"} or not p.is_file():
        continue
    t = p.read_text()
    o = t
    for a, b in literal:
        t = t.replace(a, b)
    m = dict(common)
    if "grid" in p.relative_to(dst).parts:
        m |= grid
    t = re.sub(r"(?<![\d.])(36[0-3]\d|86[0-3]\d)(?!\d)", lambda mo: m.get(mo.group(1), mo.group(1)), t)
    if t != o:
        p.write_text(t); n += 1
print("rewrote", n, "files")
