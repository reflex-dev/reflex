"""Import JavaScript modules from Python.

``from my_app.scripts.party import celebrate`` finds ``my_app/scripts/party.js``
(or ``.ts``) when no Python module of that name exists.

``import reflex`` installs the finder, so this module stays as cheap to import
as it can: ``os.path`` instead of ``pathlib``, and a finder and loader that
implement the import protocol without the ``importlib.abc`` base classes, and
no ``typing``. The event system loads with the first JavaScript module
imported.
"""

from __future__ import annotations

import os.path
import sys
from importlib.machinery import ModuleSpec

# Not imported from typing, which `import reflex` does not load otherwise.
TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.abc import Loader as _LoaderBase
    from types import ModuleType
else:
    _LoaderBase = object

# The extensions of the files a JavaScript module may be written in.
SCRIPT_EXTENSIONS = (".js", ".ts")


class _ScriptLoader(_LoaderBase):
    """Execute a JavaScript module by exposing its exports as functions."""

    def __init__(self, path: str):
        """Create the loader.

        Args:
            path: The JavaScript file.
        """
        self.path = path

    def create_module(self, spec: ModuleSpec) -> None:
        """Use the default module creation.

        Args:
            spec: The module spec.
        """

    def exec_module(self, module: ModuleType) -> None:
        """Populate the module with one function per export.

        Args:
            module: The module to populate.
        """
        # Imported here: the finder loads with `import reflex`, which must not
        # pay for the event system until a JavaScript module is imported.
        from pathlib import Path

        from reflex_base.js.modules import load_module

        load_module(module, Path(self.path))


class ScriptFinder:
    """Find a JavaScript file where no Python module of the name exists."""

    def find_spec(
        self,
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
        name = fullname.rpartition(".")[2]
        for entry in path:
            for extension in SCRIPT_EXTENSIONS:
                # Not pathlib: see the module docstring.
                file = os.path.join(entry, name + extension)  # noqa: PTH118
                if os.path.isfile(file):  # noqa: PTH113
                    return ModuleSpec(fullname, _ScriptLoader(file), origin=file)
        return None


def install() -> None:
    """Let ``import`` find JavaScript modules, after every other finder."""
    if not any(isinstance(finder, ScriptFinder) for finder in sys.meta_path):
        sys.meta_path.append(ScriptFinder())
