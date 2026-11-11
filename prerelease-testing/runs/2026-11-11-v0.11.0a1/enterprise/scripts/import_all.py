"""Import every reflex_enterprise submodule with warnings on; print warnings and errors."""
import importlib, pkgutil, sys, warnings, os, io, contextlib
import reflex
venv = os.environ["EXPECT_VENV"]
assert venv in reflex.__file__, reflex.__file__
warnings.simplefilter("default")
caught = []
def show(message, category, filename, lineno, file=None, line=None):
    caught.append(f"{category.__name__}: {message} [{filename}:{lineno}]")
warnings.showwarning = show
import reflex_enterprise
ok, bad = 0, []
for m in pkgutil.walk_packages(reflex_enterprise.__path__, "reflex_enterprise."):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            importlib.import_module(m.name)
        ok += 1
    except Exception as e:
        bad.append(f"{m.name}: {type(e).__name__}: {e}")
    out = buf.getvalue().strip()
    if out:
        print(f"OUTPUT from {m.name}: {out[:600]}")
print("reflex", reflex.__version__ if hasattr(reflex, "__version__") else "?", "imported ok:", ok)
for b in bad: print("ERROR", b)
for c in dict.fromkeys(caught): print("WARN", c[:400])
