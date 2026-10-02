"""Compiler variables."""

from enum import Enum
from types import SimpleNamespace


class Ext(SimpleNamespace):
    """Extension used in Reflex."""

    # The extension for JS files.
    JS = ".js"
    # The extension for python files.
    PY = ".py"
    # The extension for css files.
    CSS = ".css"
    # The extension for zip files.
    ZIP = ".zip"


class ComponentName(Enum):
    """Component names."""

    BACKEND = "Backend"
    FRONTEND = "Frontend"

    def zip(self):
        """Give the zip filename for the component.

        Returns:
            The lower-case filename with zip extension.

        """
        return self.value.lower() + Ext.ZIP
