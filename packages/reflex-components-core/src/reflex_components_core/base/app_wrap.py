"""Top-level component that wraps the entire app."""

from reflex_base.components.component import Component
from reflex_base.vars.base import Var

from reflex_components_core.base.fragment import Fragment


class AppWrap(Fragment):
    """Innermost (priority 0) element of the python app-wrap chain.

    Renders as ``jsx(Fragment, {}, children)`` — the chain ends here, with
    the route ``children`` JS variable flowing through. Same-priority
    siblings (e.g. ``StickyBadge``) get appended via the chain reducer and
    sit alongside ``children`` inside this Fragment.
    """

    @classmethod
    def create(cls) -> Component:
        """Create a new AppWrap component.

        Returns:
            A new AppWrap component containing {children}.
        """
        return super().create(Var(_js_expr="children"))
