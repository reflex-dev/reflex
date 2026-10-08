"""Insert a QA venv guard after `import reflex as rx` in each given rxconfig.py (idempotent)."""
import sys

GUARD = (
    "import os as _qa_os\n\n"
    '_qa_ev = _qa_os.environ.get("QA_EXPECT_VENV")\n'
    "if _qa_ev:  # QA venv guard (a5_upgrade_ent)\n"
    '    assert f"/scratchpad/envs/{_qa_ev}/" in rx.__file__, rx.__file__\n'
)
for p in sys.argv[1:]:
    s = open(p).read()
    if "QA venv guard" not in s:
        s = s.replace("import reflex as rx\n", "import reflex as rx\n" + GUARD, 1)
        open(p, "w").write(s)
    print(p, "QA venv guard" in s)
