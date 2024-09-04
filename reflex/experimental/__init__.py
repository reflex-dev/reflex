"""Namespace for experimental features."""

from types import SimpleNamespace

from reflex.components.props import PropsBase
from reflex.components.radix.themes.components.progress import progress as progress
from reflex.components.sonner.toast import toast as toast

from ..utils.console import warn
from . import hooks as hooks
from .assets import asset as asset
from .client_state import ClientStateVar as ClientStateVar
from .layout import layout as layout
from .misc import run_in_thread as run_in_thread

warn(
    "`rx._x` contains experimental features and might be removed at any time in the future .",
)

_EMITTED_PROMOTION_WARNINGS = set()


class ExperimentalNamespace(SimpleNamespace):
    """Namespace for experimental features."""

    @property
    def toast(self):
        """Temporary property returning the toast namespace.

        Remove this property when toast is fully promoted.

        Returns:
            The toast namespace.
        """
        self.register_component_warning("toast")
        return toast

    @property
    def progress(self):
        """Temporary property returning the toast namespace.

        Remove this property when toast is fully promoted.

        Returns:
            The toast namespace.
        """
        self.register_component_warning("progress")
        return progress

    @staticmethod
    def register_component_warning(component_name: str):
        """Add component to emitted warnings and throw a warning if it
        doesn't exist.

        Args:
             component_name: name of the component.
        """
        if component_name not in _EMITTED_PROMOTION_WARNINGS:
            _EMITTED_PROMOTION_WARNINGS.add(component_name)
            warn(f"`rx._x.{component_name}` was promoted to `rx.{component_name}`.")


_x = ExperimentalNamespace(
    asset=asset,
    client_state=ClientStateVar.create,
    hooks=hooks,
    layout=layout,
    PropsBase=PropsBase,
    run_in_thread=run_in_thread,
)
