"""ISSUE A on the reflex-enterprise dnd surface.

`bundle_library("d3-format")` is called ONCE, at module import time - the spelling
the reflex-enterprise error message itself recommends. `compile_app()` calls
`reset_bundled_libraries()` after this module is imported, so by the time the
page is evaluated the registration is gone and the LambdaVar validator rejects
the very import the user bundled.

    cd bundlectx_dnd && CI=1 REFLEX_TELEMETRY_ENABLED=false reflex run \
        --frontend-port 5151 --backend-port 9551

-> ValueError: Library d3-format is not bundled. Use `from reflex.components.dynamic
   import bundle_library; bundle_library('d3-format') to enable it it.
"""

from typing import Any, Mapping

import reflex as rx
from reflex.components.dynamic import bundle_library
from reflex.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData

import reflex_enterprise as rxe
from reflex_enterprise.components.dnd.dnd import DropTargetMonitor

bundle_library("d3-format")  # import-time only


def big_number_can_drop(
    item: rx.vars.ObjectVar[Mapping[str, Any]], monitor: DropTargetMonitor
):
    """can_drop whose JS needs `format` from the bundled d3-format package."""
    return Var(
        f'(format(",")({item.price}).indexOf(",") !== -1)',
        _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
    ).to(bool)


@rx.page(route="/", title="bundlectx dnd")
def index() -> rx.Component:
    return rxe.dnd.drop_target(
        rx.text("target"),
        accept=["X"],
        can_drop=big_number_can_drop,
    )


app = rxe.App()
