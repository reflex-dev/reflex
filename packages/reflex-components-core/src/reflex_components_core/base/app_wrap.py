"""Top-level component that wraps the entire app."""

from reflex_base.components.component import Component
from reflex_base.vars.base import Var


class AppWrap(Component):
    """Innermost element of the app-wrap chain.

    Renders as ``<AppWrap>{children}</AppWrap>`` — the locally-defined JS
    function in ``app_root_template`` that hosts all hooks aggregated from
    the python chain and returns its children. Library is ``None`` because
    the JS function is defined in the same file the component renders into.
    """

    library = None
    tag = "AppWrap"

    @classmethod
    def create(cls) -> Component:
        """Create a new AppWrap component.

        Returns:
            A new AppWrap component containing {children}.
        """
        return super().create(Var(_js_expr="children"))
