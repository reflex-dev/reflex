"""Does the reflex-enterprise LambdaVar path really sit inside a cached computation?

Simulates the historical rxe 0.9.4 / reflex 0.9.9a1 failure (a removed
`dynamic.bundled_libraries` module attribute) by making rxe's bundled-library
lookup raise AttributeError, then serializing a python callable nested in a list
(which is how ag_grid column defs reach the wire / the compiler).
"""

import traceback

import reflex as rx

assert "/envs/ent" in rx.__file__, rx.__file__
import reflex_enterprise  # noqa: F401,E402
from reflex_enterprise import vars as rxe_vars  # noqa: E402


def boom() -> set[str]:
    """Stand-in for the removed module attribute."""
    msg = "module 'reflex.components.dynamic' has no attribute 'bundled_libraries'"
    raise AttributeError(msg)


rxe_vars.get_bundled_libraries = boom


def cell_renderer(params: rx.Var) -> rx.Component:
    """A python-callable cell renderer, as ag_grid column defs use."""
    return rx.text("cell")


for tag, value in [
    ("top_level_callable", cell_renderer),
    ("callable_in_list_of_dicts", [{"field": "a", "cellRenderer": cell_renderer}]),
]:
    print(f"=== {tag} ===")
    try:
        print("  ->", str(rx.Var.create(value))[:80])
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        print(f"  {type(e).__module__}.{type(e).__name__}: {str(e)[:160]}")
        print(f"  real AttributeError visible: {'has no attribute' in tb and 'bundled_libraries' in tb}")
    print()
