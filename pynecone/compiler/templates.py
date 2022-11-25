"""Templates to use in the pynecone compiler."""

from typing import Optional, Set

from pynecone import constants
from pynecone.utils import join

# Template for the Pynecone config file.
PCCONFIG = f"""import pynecone as pc


config = pc.Config(
    app_name="{{app_name}}",
    bun_path="{constants.BUN_PATH}",
    db_url="{constants.DB_URL}",
    env=pc.Env.DEV,
)
"""

# Javascript formatting.
CONST = "const {name} = {value}".format
PROP = "{object}.{property}".format
IMPORT_LIB = 'import "{lib}"'.format
IMPORT_FIELDS = 'import {default}{others} from "{lib}"'.format


def format_import(lib: str, default: str = "", rest: Optional[Set[str]] = None) -> str:
    """Format an import statement.

    Args:
        lib: The library to import from.
        default: The default field to import.
        rest: The set of fields to import from the library.

    Returns:
        The compiled import statement.
    """
    # Handle the case of direct imports with no libraries.
    if lib == "":
        assert default == "", "No default field allowed for empty library."
        assert rest is not None and len(rest) > 0, "No fields to import."
        return join([IMPORT_LIB(lib=lib) for lib in sorted(rest)])

    # Handle importing from a library.
    rest = rest or set()
    if len(default) == 0 and len(rest) == 0:
        # Handle the case of importing a library with no fields.
        return IMPORT_LIB(lib=lib)
    else:
        # Handle importing specific fields from a library.
        others = f'{{{", ".join(sorted(rest))}}}' if len(rest) > 0 else ""
        if len(default) > 0 and len(rest) > 0:
            default += ", "
        return IMPORT_FIELDS(default=default, others=others, lib=lib)


# Code to render a NextJS Document root.
DOCUMENT_ROOT = join(
    [
        "{imports}",
        "export default function Document() {{",
        "return (",
        "{document}",
        ")",
        "}}",
    ]
).format

# Template for the theme file.
THEME = "export default {theme}".format

# Code to render a single NextJS component.
COMPONENT = join(
    [
        "{imports}",
        "{custom_code}",
        "{constants}",
        "export default function Component() {{",
        "{state}",
        "{events}",
        "{effects}",
        "return (",
        "{render}",
        ")",
        "}}",
    ]
).format

# React state declarations.
USE_STATE = CONST(
    name="[{state}, {set_state}]", value="useState({initial_state})"
).format


def format_state_setter(state: str) -> str:
    """Format a state setter.

    Args:
        state: The name of the state variable.

    Returns:
        The compiled state setter.
    """
    return f"set{state[0].upper() + state[1:]}"


def format_state(
    state: str,
    initial_state: str,
) -> str:
    """Format a state declaration.

    Args:
        state: The name of the state variable.
        initial_state: The initial state of the state variable.

    Returns:
        The compiled state declaration.
    """
    set_state = format_state_setter(state)
    return USE_STATE(state=state, set_state=set_state, initial_state=initial_state)


# Events.
EVENT_ENDPOINT = constants.Endpoint.EVENT.name
EVENT_FN = join(
    [
        "const Event = events => {set_state}({{",
        "  ...{state},",
        "  events: [...{state}.events, ...events],",
        "}})",
    ]
).format


# Effects.
ROUTER = constants.ROUTER
RESULT = constants.RESULT
PROCESSING = constants.PROCESSING
STATE = constants.STATE
EVENTS = constants.EVENTS
SET_RESULT = format_state_setter(RESULT)
USE_EFFECT = join(
    [
        "useEffect(() => {{",
        "  const update = async () => {{",
        f"    if ({RESULT}.{STATE} != null) {{{{",
        f"      {{set_state}}({{{{",
        f"        ...{RESULT}.{STATE},",
        f"        events: [...{{state}}.{EVENTS}, ...{RESULT}.{EVENTS}],",
        "      }})",
        f"      {SET_RESULT}({{{{",
        f"        {STATE}: null,",
        f"        {EVENTS}: [],",
        f"        {PROCESSING}: false,",
        "      }})",
        "    }}",
        f"    await updateState({{state}}, {RESULT}, {SET_RESULT}, {EVENT_ENDPOINT}, {ROUTER})",
        "  }}",
        "  update()",
        "}})",
    ]
).format

# Routing
ROUTER = f"const {constants.ROUTER} = useRouter()"
