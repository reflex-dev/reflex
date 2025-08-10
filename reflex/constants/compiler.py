"""Compiler variables."""

import dataclasses
import enum
from enum import Enum
from types import SimpleNamespace

from reflex.constants import Dirs
from reflex.utils.imports import ImportVar

# The prefix used to create setters for state vars.
SETTER_PREFIX = "set_"

# The file used to specify no compilation.
NOCOMPILE_FILE = "nocompile"


class Ext(SimpleNamespace):
    """Extension used in Reflex."""

    # The extension for JS files.
    JS = ".js"
    # The extension for JSX files.
    JSX = ".jsx"
    # The extension for python files.
    PY = ".py"
    # The extension for css files.
    CSS = ".css"
    # The extension for zip files.
    ZIP = ".zip"
    # The extension for executable files on Windows.
    EXE = ".exe"
    # The extension for markdown files.
    MD = ".md"


class CompileVars(SimpleNamespace):
    """The variables used during compilation."""

    # The expected variable name where the rx.App is stored.
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
    # The name of the function to add events to the queue.
    ADD_EVENTS = "addEvents"
    # The name of the var storing any connection error.
    CONNECT_ERROR = "connectErrors"
    # The name of the function for converting a dict to an event.
    TO_EVENT = "Event"
    # The name of the internal on_load event.
    ON_LOAD_INTERNAL = "reflex___state____on_load_internal_state.on_load_internal"
    # The name of the internal event to update generic state vars.
    UPDATE_VARS_INTERNAL = (
        "reflex___state____update_vars_internal_state.update_vars_internal"
    )
    # The name of the frontend event exception state
    FRONTEND_EXCEPTION_STATE = "reflex___state____frontend_event_exception_state"
    # The full name of the frontend exception state
    FRONTEND_EXCEPTION_STATE_FULL = (
        f"reflex___state____state.{FRONTEND_EXCEPTION_STATE}"
    )


class PageNames(SimpleNamespace):
    """The name of basic pages deployed in the frontend."""

    # The name of the index page.
    INDEX_ROUTE = "index"
    # The name of the app root page.
    APP_ROOT = "root.jsx"
    # The root stylesheet filename.
    STYLESHEET_ROOT = "__reflex_global_styles"
    # The name of the document root page.
    DOCUMENT_ROOT = "_document.js"
    # The name of the theme page.
    THEME = "theme"
    # The module containing components.
    COMPONENTS = "components"
    # The module containing shared stateful components
    STATEFUL_COMPONENTS = "stateful_components"


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


class CompileContext(str, Enum):
    """The context in which the compiler is running."""

    RUN = "run"
    EXPORT = "export"
    DEPLOY = "deploy"
    UNDEFINED = "undefined"


class Imports(SimpleNamespace):
    """Common sets of import vars."""

    EVENTS = {
        "react": [ImportVar(tag="useContext")],
        f"$/{Dirs.CONTEXTS_PATH}": [ImportVar(tag="EventLoopContext")],
        f"$/{Dirs.STATE_PATH}": [ImportVar(tag=CompileVars.TO_EVENT)],
    }


class Hooks(SimpleNamespace):
    """Common sets of hook declarations."""

    EVENTS = f"const [{CompileVars.ADD_EVENTS}, {CompileVars.CONNECT_ERROR}] = useContext(EventLoopContext);"

    class HookPosition(enum.Enum):
        """The position of the hook in the component."""

        INTERNAL = "internal"
        PRE_TRIGGER = "pre_trigger"
        POST_TRIGGER = "post_trigger"


class MemoizationDisposition(enum.Enum):
    """The conditions under which a component should be memoized."""

    # If the component uses state or events, it should be memoized.
    STATEFUL = "stateful"
    ALWAYS = "always"
    NEVER = "never"


@dataclasses.dataclass(frozen=True)
class MemoizationMode:
    """The mode for memoizing a Component."""

    # The conditions under which the component should be memoized.
    disposition: MemoizationDisposition = MemoizationDisposition.STATEFUL

    # Whether children of this component should be memoized first.
    recursive: bool = True


DATA_UNDERSCORE = "data_"
DATA_DASH = "data-"
ARIA_UNDERSCORE = "aria_"
ARIA_DASH = "aria-"

SPECIAL_ATTRS = (
    DATA_UNDERSCORE,
    DATA_DASH,
    ARIA_UNDERSCORE,
    ARIA_DASH,
)


class SpecialAttributes(enum.Enum):
    """Special attributes for components.

    These are placed in custom_attrs and rendered as-is rather than converting
    to a style prop.
    """

    @classmethod
    def is_special(cls, attr: str) -> bool:
        """Check if the attribute is special.

        Args:
            attr: the attribute to check

        Returns:
            True if the attribute is special.
        """
        return attr.startswith(SPECIAL_ATTRS)


class ResetStylesheet(SimpleNamespace):
    """Constants for CSS reset stylesheet."""

    # The filename of the CSS reset file.
    FILENAME = "__reflex_style_reset.css"
