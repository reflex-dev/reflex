"""Reflex core types."""

from __future__ import annotations

import sys
from importlib.machinery import PathFinder

# Not imported from typing, which `import reflex` does not load otherwise.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType


class _ScriptFinder:
    """Let app code import the JavaScript modules beside it.

    Registered here, by the package every Reflex import loads first, so that
    no module is loaded for it: the real finder, ``reflex_base.js.finder``,
    loads on the first import of a submodule that is no Python module.
    Registered before ``PathFinder``, whose search it runs first, so that a
    directory without ``__init__.py`` does not hide a JavaScript module of its
    name.
    """

    @staticmethod
    def find_spec(
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find a submodule, or else the JavaScript file for it.

        Args:
            fullname: The dotted module name.
            path: The search path of the parent package; None for a top-level
                module, which is never a JavaScript module.
            target: The module being reloaded, if any.

        Returns:
            The spec of the Python module, else of the JavaScript module, else
            of the namespace package, or None.
        """
        if path is None:
            return None
        spec = PathFinder.find_spec(fullname, path, target)
        # A spec without an origin is a namespace package: a directory without
        # `__init__.py`, which is no Python module.
        if spec is not None and spec.origin is not None:
            return spec
        from reflex_base.js.finder import find_spec

        return find_spec(fullname, path) or spec


# By name, not identity: importing this module afresh, as a reload or a
# benchmark that clears sys.modules does, must not register a second one. Last
# when a wrapper has replaced PathFinder, where a directory hides a script again.
if not any(
    isinstance(finder, type) and finder.__qualname__ == "_ScriptFinder"
    for finder in sys.meta_path
):
    sys.meta_path.insert(
        sys.meta_path.index(PathFinder)
        if PathFinder in sys.meta_path
        else len(sys.meta_path),
        _ScriptFinder,
    )
