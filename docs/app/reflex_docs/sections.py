"""Assign each docs route to its navbar tab and sidebar section.

Sections are decided at build time from a route's first path segment, so the
prerendered HTML of every page already marks the right tab and sidebar, and a
route whose later segments merely contain a section's name (such as
``/wrapping-react/library-and-tags/``) stays in its own section.
"""

import json

import reflex as rx

OVERVIEW = "overview"
AI = "ai"
FRAMEWORK = "framework"
COMPONENTS = "components"
API_REFERENCE = "api-reference"
ENTERPRISE = "enterprise"
CLOUD = "cloud"
XY = "xy"

_SECTION_BY_SEGMENT = {
    "": OVERVIEW,
    "ai": AI,
    "library": COMPONENTS,
    "api-reference": API_REFERENCE,
    "changelog": API_REFERENCE,
    "enterprise": ENTERPRISE,
    "hosting": CLOUD,
    "xy": XY,
}

# Sidebar sections that the navbar groups under its Framework tab.
_FRAMEWORK_SECTIONS = frozenset({FRAMEWORK, COMPONENTS, API_REFERENCE, ENTERPRISE})


def docs_section(path: str) -> str:
    """Get the sidebar section of a docs route.

    Args:
        path: The app-relative route, such as ``/library/forms/button/``.

    Returns:
        The section owning the route's first path segment, or the Framework
        section for the guides that have no section prefix of their own.
    """
    segment = path.strip("/").split("/", 1)[0]
    return _SECTION_BY_SEGMENT.get(segment, FRAMEWORK)


def docs_section_var(path: rx.vars.StringVar[str]) -> rx.vars.StringVar[str]:
    """Get the sidebar section of a docs route on the client, like ``docs_section``.

    Lets a component that follows client-side navigation pick the section
    itself, instead of receiving it from each page at build time.

    Args:
        path: The normalized app-relative route, with leading and trailing slashes.

    Returns:
        The section owning the route's first path segment, or the Framework
        section for the guides that have no section prefix of their own.
    """
    table = json.dumps(_SECTION_BY_SEGMENT, sort_keys=True)
    return rx.Var(
        f"((sections, segment) => Object.hasOwn(sections, segment) ? sections[segment] : "
        f'{json.dumps(FRAMEWORK)})({table}, {path}.split("/")[1])',
        _var_type=str,
        _var_data=path._get_all_var_data(),
    ).to(str)


def navbar_tab(path: str) -> str:
    """Get the navbar tab that is current on a docs route.

    Args:
        path: The app-relative route.

    Returns:
        The navbar tab whose section contains the route.
    """
    section = docs_section(path)
    return FRAMEWORK if section in _FRAMEWORK_SECTIONS else section
