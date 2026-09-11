"""Module A: four custom components whose qualnames match module B's exactly.

Generated from ``custom_template.py.in``. ``custom_a.py`` and ``custom_b.py``
define the *same four class names* with the *same render*; each pair differs in
exactly one non-rendered artifact:

- ``CodeWidget``  -> ``add_custom_code``
- ``DynWidget``   -> ``_get_dynamic_imports``
- ``CssWidget``   -> a tagless ``ImportVar`` (side-effect CSS import)
- ``WrapWidget``  -> ``_get_app_wrap_components``

Every widget binds the same shared state var so the compiler auto-memoizes it.
"""

import reflex as rx
from reflex_base.utils.imports import ImportVar

from .common import Shared


class CodeWidget(rx.el.Div):
    """Identical render in both modules; only ``add_custom_code`` differs."""

    def add_custom_code(self) -> list[str]:
        """Emit a module-level marker.

        Returns:
            The custom code.
        """
        return ["globalThis.MEMO_CODE_A = 'code-A';"]


class DynWidget(rx.el.Div):
    """Identical render in both modules; only ``_get_dynamic_imports`` differs."""

    def _get_dynamic_imports(self) -> str:
        """Emit a module-level dynamic-import slot marker.

        Returns:
            The dynamic import statement.
        """
        return "const MEMO_DYN_A = (globalThis.MEMO_DYN_A = 'dyn-A');"


class CssWidget(rx.el.Div):
    """Identical render in both modules; only a tagless ImportVar differs."""

    def add_imports(self):
        """Side-effect import of this module's stylesheet.

        Returns:
            The import dict.
        """
        return {"$/public/memo_a.css": [ImportVar(tag=None)]}


class WrapWidget(rx.el.Div):
    """Identical render in both modules; only the app-wrap component differs."""

    @staticmethod
    def _get_app_wrap_components():
        """Contribute an app-wrap component.

        Returns:
            The app wrap dict.
        """
        return {(61, "MemoWrapA"): rx.text("a")}


def widgets() -> rx.Component:
    """Render one of each widget, all binding the same shared var.

    Returns:
        The stack of widgets.
    """
    return rx.el.div(
        CodeWidget.create("code:", title=Shared.label),
        DynWidget.create("dyn:", title=Shared.label),
        CssWidget.create("css:", title=Shared.label, class_name="memo-css-target"),
        WrapWidget.create("wrap:", title=Shared.label),
    )
