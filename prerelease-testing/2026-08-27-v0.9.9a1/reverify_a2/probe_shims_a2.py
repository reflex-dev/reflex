"""Offline probes for the 0.9.9a2 deprecation shims (PRs #6967/#6985).

Checks, against PyPI reflex==0.9.9a2 + reflex-enterprise==0.9.4:
1. reflex.components.dynamic.bundled_libraries is readable again (FINDING-001 shim).
2. from reflex.page import DECORATED_PAGES works again (FINDING-023 shim).
3. rxe LiteralLambdaVar.create with a component-returning lambda no longer raises
   (FINDING-021 direct proof, formerly AttributeError at reflex_enterprise/vars.py:143).
DeprecationWarnings are captured and printed, not suppressed.
"""

import importlib.metadata as md
import sys
import traceback
import warnings

results = []


def check(name, fn):
    """Run one probe, recording pass/fail and any warnings it emits."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            out = fn()
            status = "PASS"
        except Exception:
            traceback.print_exc()
            out = None
            status = "FAIL"
    wlist = [f"{w.category.__name__}: {w.message}" for w in caught]
    results.append((name, status, out, wlist))
    print(f"[{status}] {name} -> {out!r}")
    for w in wlist:
        print(f"    warning: {w}")


print(
    "reflex", md.version("reflex"),
    "| reflex-base", md.version("reflex-base"),
    "| reflex-enterprise", md.version("reflex-enterprise"),
)

import reflex as rx  # noqa: E402
import reflex_enterprise  # noqa: E402  (ensure rxe importable)

assert "reverify_ent/venv" in rx.__file__, rx.__file__
assert "reverify_ent/venv" in reflex_enterprise.__file__, reflex_enterprise.__file__


def probe_bundled_libraries():
    from reflex.components import dynamic

    libs = dynamic.bundled_libraries
    return type(libs).__name__, sorted(libs)[:4], len(list(libs))


def probe_decorated_pages():
    from reflex.page import DECORATED_PAGES

    return type(DECORATED_PAGES).__name__


def probe_lambda_var_bare():
    """Outside app-compile context, rxe's DESIGNED validation must fire.

    On 0.9.9a1 this raised AttributeError (bundled_libraries gone). With the shim
    it must reach rxe's intended 'Library @radix-ui/themes is not bundled'
    ValueError — the same behavior 0.9.8 has outside compile context (see
    ent_aggrid NOTES.md verification point 4).

    Returns:
        Marker string describing which designed path fired.

    Raises:
        AssertionError: if the 0.9.9a1 AttributeError path is still reachable.
    """
    from reflex_enterprise.vars import LiteralLambdaVar

    try:
        LiteralLambdaVar.create(lambda params: rx.text(params.value, color="tomato"))
    except AttributeError as e:
        raise AssertionError(f"a1 bug still present: {e}") from e
    except ValueError as e:
        assert "is not bundled" in str(e), str(e)
        return "designed 'not bundled' ValueError (matches 0.9.8 behavior)"
    return "created without validation error"


def probe_lambda_var_bundled():
    from reflex.components.dynamic import bundle_library
    from reflex_enterprise.vars import LiteralLambdaVar

    bundle_library("@radix-ui/themes")
    v = LiteralLambdaVar.create(lambda params: rx.text(params.value, color="tomato"))
    return type(v).__name__, str(v)[:80]


check("dynamic.bundled_libraries (FINDING-001/022 shim)", probe_bundled_libraries)
check("reflex.page.DECORATED_PAGES import (FINDING-023 shim)", probe_decorated_pages)
check("LiteralLambdaVar.create bare (FINDING-021: no AttributeError)", probe_lambda_var_bare)
check("LiteralLambdaVar.create after bundle_library (FINDING-021)", probe_lambda_var_bundled)

fails = [r for r in results if r[1] == "FAIL"]
print("\nSUMMARY:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
