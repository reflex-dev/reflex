"""Import JavaScript modules from Python.

``from my_app.scripts.party import celebrate`` finds ``my_app/scripts/party.js``
(or ``.ts``) when no Python module of that name exists and ``my_app`` is the
app's package. Other packages' JavaScript files are never imported.

``import reflex`` registers a small finder that loads this module on the first
import of a submodule no other finder found, which can happen while ``reflex``
itself loads, so it stays cheap: ``os.path`` instead of ``pathlib``, a loader
that implements the import protocol without the ``importlib.abc`` base class,
and no ``typing``. The config loads once a JavaScript file is found, and the
event system with the first JavaScript module imported.
"""

from __future__ import annotations

import os.path
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
    """Execute a JavaScript module: register it, and make its names functions."""

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
        """Register the module, whose names become functions on first use.

        Args:
            module: The module to populate.
        """
        # Imported here: loading the finder must not load the event system,
        # which only a JavaScript module being imported needs.
        from pathlib import Path

        from reflex_base.js.modules import _load_module

        _load_module(module, Path(self.path))


def _app_package() -> str:
    """Get the name of the app's top-level package.

    Returns:
        The package ``rxconfig.py`` names, or an empty string without one.
    """
    # Imported here: the config loads only once a JavaScript file is found.
    from reflex_base.config import get_config

    return get_config().module.partition(".")[0]


def find_spec(fullname: str, path: Sequence[str]) -> ModuleSpec | None:
    """Find the JavaScript file for a submodule of the app's package.

    Args:
        fullname: The dotted module name.
        path: The search path of the parent package.

    Returns:
        The spec of the JavaScript module, or None if there is no such file or
        it is outside the app's package.
    """
    name = fullname.rpartition(".")[2]
    for entry in path:
        for extension in SCRIPT_EXTENSIONS:
            # Not pathlib: see the module docstring.
            file = os.path.join(entry, name + extension)  # noqa: PTH118
            if os.path.isfile(file):  # noqa: PTH113
                if fullname.partition(".")[0] != _app_package():
                    return None
                return ModuleSpec(fullname, _ScriptLoader(file), origin=file)
    return None
