"""Independent verification: rxe dnd non-static can_drop + module-scope bundle_library.

BUNDLE_WHERE=module (default) -> bundle_library() only at app-module import time.
BUNDLE_WHERE=page             -> the same call repeated inside the page function.
"""

import os
from typing import Any, Mapping

import reflex as rx

assert "/envs/" in rx.__file__ and "/home/user/reflex/reflex" not in rx.__file__, rx.__file__
print("PROBE venv reflex=", rx.__file__, flush=True)

from reflex.components.dynamic import bundle_library
from reflex.utils.imports import ImportVar
from reflex_base.registry import RegistrationContext
from reflex_base.vars.base import Var, VarData

import reflex_enterprise as rxe
from reflex_enterprise.components.dnd.dnd import DropTargetMonitor

WHERE = os.environ.get("BUNDLE_WHERE", "module")

bundle_library("d3-format")


def snap(label: str) -> None:
    ctx = RegistrationContext.ensure_context()
    print(
        f"PROBE {label:<10} ctx={hex(id(ctx))} bundled={sorted(ctx.bundled_libraries)}",
        flush=True,
    )


snap("import")


def price_has_comma(
    item: rx.vars.ObjectVar[Mapping[str, Any]], monitor: DropTargetMonitor
):
    """can_drop whose compiled JS needs `format` from the bundled d3-format package."""
    return Var(
        f'(format(",")({item.price}).indexOf(",") !== -1)',
        _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
    ).to(bool)


@rx.page(route="/", title="dndbundle")
def index() -> rx.Component:
    if WHERE == "page":
        bundle_library("d3-format")
    snap("page_eval")
    return rxe.dnd.drop_target(
        rx.text("target"),
        accept=["X"],
        can_drop=price_has_comma,
    )


app = rxe.App()
snap("after_app")
