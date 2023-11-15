"""Compiler variables."""
from enum import Enum
from types import SimpleNamespace

# The prefix used to create setters for state vars.
SETTER_PREFIX = "set_"

# The file used to specify no compilation.
NOCOMPILE_FILE = ".web/nocompile"


class Ext(SimpleNamespace):
    """Extension used in Nextpy."""

    # The extension for JS files.
    JS = ".js"
    # The extension for python files.
    PY = ".py"
    # The extension for css files.
    CSS = ".css"
    # The extension for zip files.
    ZIP = ".zip"


class CompileVars(SimpleNamespace):
    """The variables used during compilation."""

    # The expected variable name where the xt.App is stored.
    APP = "app"
    # The expected variable name where the API object is stored for deployment.
    API = "api"
    # The name of the router variable.
    ROUTER = "router"
    # The name of the socket variable.
    SOCKET = "socket"
    # The name of the variable to hold API results.
    RESULT = "result"
    # The name of the final variable.
    FINAL = "final"
    # The name of the process variable.
    PROCESSING = "processing"
    # The name of the state variable.
    STATE = "state"
    # The name of the events variable.
    EVENTS = "events"
    # The name of the initial hydrate event.
    HYDRATE = "hydrate"
    # The name of the is_hydrated variable.
    IS_HYDRATED = "is_hydrated"


class PageNames(SimpleNamespace):
    """The name of basic pages deployed in NextJS."""

    # The name of the index page.
    INDEX_ROUTE = "index"
    # The name of the app root page.
    APP_ROOT = "_app"
    # The root stylesheet filename.
    STYLESHEET_ROOT = "styles"
    # The name of the document root page.
    DOCUMENT_ROOT = "_document"
    # The name of the theme page.
    THEME = "theme"


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
