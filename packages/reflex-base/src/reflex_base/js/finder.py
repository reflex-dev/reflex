"""Import JavaScript modules from Python.

``from my_app.scripts.party import celebrate`` finds ``my_app/scripts/party.js``
(or ``.ts``) when no Python module of that name exists. This module only uses
the standard library: ``import reflex`` installs the finder, and loading the
event system is left to the first JavaScript module imported.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

# The extensions of the files a JavaScript module may be written in.
SCRIPT_EXTENSIONS = (".js", ".ts")


class _ScriptLoader(importlib.abc.Loader):
    """Execute a JavaScript module by exposing its exports as functions."""

    def __init__(self, path: Path):
        """Create the loader.

        Args:
            path: The JavaScript file.
        """
        self.path = path

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> None:
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
        from reflex_base.js.modules import load_module

        load_module(module, self.path)


class ScriptFinder(importlib.abc.MetaPathFinder):
    """Find a JavaScript file where no Python module of the name exists."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
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
                file = Path(entry, name + extension)
                if file.is_file():
                    return importlib.machinery.ModuleSpec(
                        fullname, _ScriptLoader(file), origin=str(file)
                    )
        return None


def install() -> None:
    """Let ``import`` find JavaScript modules, after every other finder."""
    if not any(isinstance(finder, ScriptFinder) for finder in sys.meta_path):
        sys.meta_path.append(ScriptFinder())
