"""Namespace for experimental features."""

from types import SimpleNamespace

from reflex.components.radix.themes.components.progress import progress as progress
from reflex.components.sonner.toast import toast as toast

from ..utils.console import warn
from . import hooks as hooks
from .layout import layout as layout
from .misc import run_in_thread as run_in_thread

warn(
    "`rx._x` contains experimental features and might be removed at any time in the future .",
)

_x = SimpleNamespace(
    hooks=hooks,
    layout=layout,
    progress=progress,
    run_in_thread=run_in_thread,
    toast=toast,
)
