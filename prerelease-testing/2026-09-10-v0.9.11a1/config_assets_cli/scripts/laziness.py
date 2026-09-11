"""Report which heavy modules are pulled in by `import reflex` and whether the
lazy accessors still resolve. Run with the venv python from a NEUTRAL cwd."""
import sys, os
import reflex
assert "/envs/" in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__)
PREFIXES = ("sqlalchemy", "sqlmodel", "reflex_base.plugins", "reflex_base.compiler")
loaded = sorted(m for m in sys.modules if m.startswith(PREFIXES))
print("after import reflex ->", loaded)
print("nmodules:", len(sys.modules))
# plugins still resolve?
import reflex as rx
names = [n for n in dir(rx.plugins) if not n.startswith("_")]
print("rx.plugins names:", names)
for n in names:
    obj = getattr(rx.plugins, n)
    print("   ", n, "->", type(obj).__name__, getattr(obj, "__module__", ""))
loaded2 = sorted(m for m in sys.modules if m.startswith(PREFIXES))
print("after touching rx.plugins ->", loaded2)
print("nmodules:", len(sys.modules))
