"""Hatch plugin registration for reflex-pyi build hook."""

from hatchling.plugin import hookimpl

from hatch_reflex_pyi.plugin import ReflexPyiBuildHook


@hookimpl
def hatch_register_build_hook():
    """Register the reflex-pyi build hook."""
    return ReflexPyiBuildHook
