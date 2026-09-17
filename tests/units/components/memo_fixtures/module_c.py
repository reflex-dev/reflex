"""Cross-module memo fixture C.

``consumer`` references ``module_a.my_widget`` (a cross-module memo-to-memo
dependency), and this module also defines its own ``my_widget`` sharing the name
with ``module_a``/``module_b``. Together these cover a grouped memo file that
both imports another module's memo and exports its own same-named one.
"""

import reflex as rx
from tests.units.components.memo_fixtures import module_a


@rx.memo
def consumer(title: rx.Var[str]) -> rx.Component:
    """A memo whose body depends on ``module_a.my_widget``.

    Args:
        title: The title forwarded to the dependency.

    Returns:
        A box wrapping ``module_a.my_widget``.
    """
    return rx.box(module_a.my_widget(title=title), rx.text("c-consumer"))


@rx.memo
def my_widget(title: rx.Var[str]) -> rx.Component:
    """Same name as ``module_a.my_widget`` but defined in this module.

    Args:
        title: The title to render.

    Returns:
        A text component.
    """
    return rx.text("module_c:", title)
