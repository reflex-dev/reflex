"""Namespace for experimental features."""

from types import SimpleNamespace

from ..utils.console import warn
from . import hooks as hooks

warn(
    "`rx._x` contains experimental features and might be removed at any time in the future .",
)

_x = SimpleNamespace(
    hooks=hooks,
)
