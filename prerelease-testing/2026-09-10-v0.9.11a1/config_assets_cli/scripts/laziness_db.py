"""With reflex[db] installed, show what `import reflex` / touching types pulls in."""
import sys, time
import reflex
assert "/envs/" in reflex.__file__, reflex.__file__
PRE = ("sqlalchemy", "sqlmodel", "reflex_base.plugins", "reflex_base.compiler")
def snap(label):
    hits = sorted(m for m in sys.modules if m.startswith(PRE))
    tops = sorted({m.split(".")[0] for m in hits})
    print(f"{label}: nmodules={len(sys.modules)} matched={len(hits)} tops={tops}")
snap("after import reflex")
import reflex_base.utils.types  # noqa
snap("after import reflex_base.utils.types")
class S(reflex.State):
    x: int = 0
snap("after defining a State")
import reflex as rx
_ = rx.plugins.TailwindV4Plugin
snap("after rx.plugins.TailwindV4Plugin")
