"""Route constants."""

import re
from types import SimpleNamespace


class RouteArgType(SimpleNamespace):
    """Type of dynamic route arg extracted from URI route."""

    # Typecast to str is needed for Enum to work.
    SINGLE = str("arg_single")
    LIST = str("arg_list")


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


class RouteRegex(SimpleNamespace):
    """Regex used for extracting route args in route."""

    ARG = re.compile(r"\[(?!\.)([^\[\]]+)\]")
    # group return the catchall pattern (i.e. "[[..slug]]")
    CATCHALL = re.compile(r"(\[?\[\.{3}(?![0-9]).*\]?\])")
    # group return the arg name (i.e. "slug")
    STRICT_CATCHALL = re.compile(r"\[\.{3}([a-zA-Z_][\w]*)\]")
    # group return the arg name (i.e. "slug") (optional arg can be empty)
    OPT_CATCHALL = re.compile(r"\[\[\.{3}([a-zA-Z_][\w]*)\]\]")


class DefaultPage(SimpleNamespace):
    """Default page constants."""

    # The default title to show for Nextpy apps.
    TITLE = "Nextpy App"
    # The default description to show for Nextpy apps.
    DESCRIPTION = "A Nextpy app."
    # The default image to show for Nextpy apps.
    IMAGE = "favicon.ico"
    # The default meta list to show for Nextpy apps.
    META_LIST = []


# 404 variables
class Page404(SimpleNamespace):
    """Page 404 constants."""

    SLUG = "404"
    TITLE = "404 - Not Found"
    IMAGE = "favicon.ico"
    DESCRIPTION = "The page was not found"


ROUTE_NOT_FOUND = "routeNotFound"
