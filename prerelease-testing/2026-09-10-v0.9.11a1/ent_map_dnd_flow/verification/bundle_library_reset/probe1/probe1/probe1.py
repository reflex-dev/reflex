"""Independent verification probe (written from the claim text, not copied).

Pure reflex, no reflex-enterprise. Registers a library at module scope and
reports the active RegistrationContext id + bundled list at three moments.
Also exercises a *user-visible* pure-reflex consumer: a var-returning
``@rx.memo`` that imports from the module-scope-bundled library.
"""

import os

import reflex as rx

assert "/envs/" in rx.__file__ and "/home/user/reflex/reflex" not in rx.__file__, rx.__file__
print("PROBE venv reflex=", rx.__file__, flush=True)

from reflex.components.dynamic import bundle_library
from reflex_base.registry import RegistrationContext
from reflex_base.vars.base import Var, VarData
from reflex.utils.imports import ImportVar


def snap(label: str) -> None:
    ctx = RegistrationContext.ensure_context()
    print(
        f"PROBE {label:<10} ctx={hex(id(ctx))} bundled={sorted(ctx.bundled_libraries)}",
        flush=True,
    )


bundle_library("d3-format")
snap("import")

WHERE = os.environ.get("BUNDLE_WHERE", "module")


@rx.memo
def fmt_label(value: rx.Var[int]) -> rx.Var[str]:
    """Var-returning memo whose JS imports `format` from d3-format."""
    return Var(
        f'format(",")({value})',
        _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
    ).to(str)


@rx.page(route="/")
def index() -> rx.Component:
    if WHERE == "page":
        bundle_library("d3-format")
    snap("page_eval")
    return rx.box(fmt_label(value=1234567))


app = rx.App()
snap("after_app")
