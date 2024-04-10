"""Namespace for experimental features."""

from types import SimpleNamespace

from ..utils.console import warn
from . import hooks as hooks
from .layout import layout as layout

warn(
    "`rx._x` contains experimental features and might be removed at any time in the future .",
)

_x = SimpleNamespace(
    hooks=hooks,
    layout=layout,
)
