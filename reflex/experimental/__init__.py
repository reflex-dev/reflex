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
        if "toast" not in _EMITTED_PROMOTION_WARNINGS:
            _EMITTED_PROMOTION_WARNINGS.add("toast")
            warn(f"`rx._x.toast` was promoted to `rx.toast`.")
        return toast


_x = ExperimentalNamespace(
    asset=asset,
    client_state=ClientStateVar.create,
    hooks=hooks,
    layout=layout,
    progress=progress,
    PropsBase=PropsBase,
    run_in_thread=run_in_thread,
)
