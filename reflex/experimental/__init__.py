"""Namespace for experimental features."""

from types import SimpleNamespace

from . import hooks as hooks

_x = SimpleNamespace(
    hooks=hooks,
)
