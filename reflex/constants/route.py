"""Route constants."""

import re
from types import SimpleNamespace


class RouteArgType(SimpleNamespace):
    """Type of dynamic route arg extracted from URI route."""

    SINGLE = "arg_single"
    LIST = "arg_list"


# the name of the backend var containing path and client information
ROUTER = "router"
ROUTER_DATA = "router_data"


class RouteVar(SimpleNamespace):
    """Names of variables used in the router_data dict stored in State."""

    CLIENT_IP = "ip"
    CLIENT_TOKEN = "token"
    HEADERS = "headers"
    PATH = "pathname"
    ORIGIN = "asPath"
    SESSION_ID = "sid"
    QUERY = "query"
    COOKIE = "cookie"


# This subset of router_data is included in chained on_load events.
ROUTER_DATA_INCLUDE = {RouteVar.PATH, RouteVar.ORIGIN, RouteVar.QUERY}


class RouteRegex(SimpleNamespace):
    """Regex used for extracting route args in route."""

    _DOT_DOT_DOT = r"\.\.\."
    _OPENING_BRACKET = r"\["
    _CLOSING_BRACKET = r"\]"
    _ARG_NAME = r"[a-zA-Z_]\w*"

    # The regex for a valid arg name, e.g. "slug" in "[slug]"
    _ARG_NAME_PATTERN = re.compile(_ARG_NAME)

    SLUG = re.compile(r"[a-zA-Z0-9_-]+")
    # match a single arg (i.e. "[slug]"), returns the name of the arg
    ARG = re.compile(rf"{_OPENING_BRACKET}({_ARG_NAME}){_CLOSING_BRACKET}")
    # match a single optional arg (i.e. "[[slug]]"), returns the name of the arg
    OPTIONAL_ARG = re.compile(
        rf"{_OPENING_BRACKET * 2}({_ARG_NAME}){_CLOSING_BRACKET * 2}"
    )

    # match a single non-optional catch-all arg (i.e. "[...slug]"), returns the name of the arg
    STRICT_CATCHALL = re.compile(
        rf"{_OPENING_BRACKET}{_DOT_DOT_DOT}({_ARG_NAME}){_CLOSING_BRACKET}"
    )

    # match a single optional catch-all arg (i.e. "[[...slug]]"), returns the name of the arg
    OPTIONAL_CATCHALL = re.compile(
        rf"{_OPENING_BRACKET * 2}{_DOT_DOT_DOT}({_ARG_NAME}){_CLOSING_BRACKET * 2}"
    )

    SPLAT_CATCHALL = "[[...splat]]"
    SINGLE_SEGMENT = "__SINGLE_SEGMENT__"
    DOUBLE_SEGMENT = "__DOUBLE_SEGMENT__"
    DOUBLE_CATCHALL_SEGMENT = "__DOUBLE_CATCHALL_SEGMENT__"


class DefaultPage(SimpleNamespace):
    """Default page constants."""

    # The default title to show for Reflex apps.
    TITLE = "{} | {}"
    # The default description to show for Reflex apps.
    DESCRIPTION = ""
    # The default image to show for Reflex apps.
    IMAGE = "favicon.ico"
    # The default meta list to show for Reflex apps.
    META_LIST = []


# 404 variables
class Page404(SimpleNamespace):
    """Page 404 constants."""

    SLUG = "404"
    TITLE = "404 - Not Found"
    IMAGE = "favicon.ico"
    DESCRIPTION = "The page was not found"


ROUTE_NOT_FOUND = "routeNotFound"
