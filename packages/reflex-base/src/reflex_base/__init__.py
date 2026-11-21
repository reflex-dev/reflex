"""Reflex core types."""

from __future__ import annotations

import sys

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
    loads on the first import of a submodule no other finder found.
    """

    @staticmethod
    def find_spec(
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find the JavaScript file for a submodule.

        Args:
            fullname: The dotted module name.
            path: The search path of the parent package; None for a top-level
                module, which is never a JavaScript module.
            target: Unused.

        Returns:
            The spec of the JavaScript module, or None.
        """
        if path is None:
            return None
        from reflex_base.js.finder import find_spec

        return find_spec(fullname, path)


# By name, not identity: importing this module afresh, as a reload or a
# benchmark that clears sys.modules does, must not register a second one.
if not any(
    isinstance(finder, type) and finder.__qualname__ == "_ScriptFinder"
    for finder in sys.meta_path
):
    sys.meta_path.append(_ScriptFinder)
