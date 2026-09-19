"""Offline probe: are the 0.9.9a1 enterprise breakages (FINDING-001/021/022/023) fixed?

Run from a neutral cwd with the venv python that has reflex 0.9.11a1 + reflex-enterprise 0.9.5.
"""

import sys
import traceback

import reflex as rx

assert "/envs/" in rx.__file__ or "/venv" in rx.__file__, rx.__file__
print("reflex module:", rx.__file__)

import importlib.metadata as md

for p in ("reflex", "reflex-base", "reflex-enterprise"):
    print(f"  {p}=={md.version(p)}")

results = {}


def check(name, fn):
    try:
        val = fn()
        results[name] = ("OK", repr(val)[:200])
    except Exception as e:
        results[name] = (f"{type(e).__name__}", str(e)[:300])
        if "-v" in sys.argv:
            traceback.print_exc()


# FINDING-001/008: reflex.components.dynamic.bundled_libraries removed in 0.9.9a1
def _bundled():
    from reflex.components import dynamic

    return dynamic.bundled_libraries


check("reflex.components.dynamic.bundled_libraries", _bundled)


# FINDING-023: reflex.page.DECORATED_PAGES removed in 0.9.9a1
def _decorated():
    from reflex.page import DECORATED_PAGES

    return type(DECORATED_PAGES)


check("reflex.page.DECORATED_PAGES", _decorated)


# rxe compat shim
def _rxe_shim():
    from reflex_enterprise.vars import get_bundled_libraries

    return sorted(get_bundled_libraries())[:5]


check("reflex_enterprise.vars.get_bundled_libraries()", _rxe_shim)


# FINDING-021 core: LiteralLambdaVar.create on a callable whose return expr carries imports
def _lambda_component():
    import reflex_enterprise as rxe  # noqa: F401
    from reflex.components import dynamic
    from reflex_enterprise.vars import LiteralLambdaVar

    dynamic.bundle_library("@radix-ui/themes")
    v = LiteralLambdaVar.create(
        lambda params: rx.text(params.value, color="rebeccapurple")
    )
    return str(v)[:150]


check("LiteralLambdaVar.create(lambda -> rx.text(...))", _lambda_component)


def _lambda_dict_get():
    import reflex_enterprise as rxe  # noqa: F401
    from reflex_enterprise.vars import LiteralLambdaVar

    def flag_formatter(params):
        return rx.Var.create({"USA": "US", "Sweden": "SE"}).get(
            params.value.to(str), "??"
        )

    v = LiteralLambdaVar.create(flag_formatter)
    return str(v)[:150]


check("LiteralLambdaVar.create(dict .get formatter)", _lambda_dict_get)


def _lambda_noimports():
    from reflex_enterprise.vars import LiteralLambdaVar

    v = LiteralLambdaVar.create(lambda params: round(params.value.to(float), 4))
    return str(v)[:150]


check("LiteralLambdaVar.create(round formatter, no imports)", _lambda_noimports)


print("\n== RESULTS ==")
for k, (status, detail) in results.items():
    print(f"{status:32s} {k}\n{'':32s}   {detail}")
