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


def promoted(cls, name=None):
    """Apply decorator on all method of the class to warn about the feature being promoted.

    Args:
        cls: The class to promote.
        name: The name of the class.

    Returns:
        The promoted class.
    """
    feature_name = name or cls.__call__.__name__

    def wrapper(method):
        def inner(*args, **kwargs):
            if feature_name not in _EMITTED_PROMOTION_WARNINGS:
                _EMITTED_PROMOTION_WARNINGS.add(feature_name)
                warn(f"`rx._x.{feature_name}` was promoted to `rx.{feature_name}`.")
            return method(*args, **kwargs)

        return inner

    for attr in dir(cls):
        if attr.startswith("__"):
            continue
        setattr(cls, attr, wrapper(getattr(cls, attr)))

    return cls


_x = SimpleNamespace(
    asset=asset,
    client_state=ClientStateVar.create,
    hooks=hooks,
    layout=layout,
    progress=progress,
    PropsBase=PropsBase,
    run_in_thread=run_in_thread,
    toast=promoted(toast, name="toast"),
)
