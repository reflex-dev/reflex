"""Direct probe: does LiteralLambdaVar choke on a component-returning lambda?

Step 1: check whether reflex.components.dynamic has module attr bundled_libraries.
Step 2: LiteralLambdaVar.create(lambda) -> _js_expr forces the cached var computation.
Step 3: unwrap the masked error by calling the cached function directly.
"""

import traceback

import reflex as rx
from reflex.components import dynamic

print("has bundled_libraries attr:", hasattr(dynamic, "bundled_libraries"))

from reflex_enterprise.vars import LiteralLambdaVar

v = LiteralLambdaVar.create(lambda params: rx.text(params.value, color="tomato"))
print("created:", type(v).__name__)

try:
    print("js:", str(v))
except Exception as e:
    print("MASKED ERROR:", type(e).__module__ + "." + type(e).__name__, "-", e)

# Now bypass the cached_property descriptor to see the real error.
try:
    # find the underlying function of the cached property on the class
    import reflex_base.vars.base as vb

    cp = None
    for klass in type(v).__mro__:
        cp = klass.__dict__.get("_cached_var_name")
        if cp is not None:
            break
    fn = getattr(cp, "func", None) or getattr(cp, "fget", None) or cp
    fn(v)
    print("no error from direct call?!")
except Exception:
    print("REAL ERROR (direct call of cached fn):")
    traceback.print_exc()
