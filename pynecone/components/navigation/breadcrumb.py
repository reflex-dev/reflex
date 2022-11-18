"""Breadcrumb components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Breadcrumb(ChakraComponent):
    """The parent container for breadcrumbs."""

    tag = "Breadcrumb"

    # The visual separator between each breadcrumb item
    separator: Var[str]

    # The left and right margin applied to the separator
    separator_margin: Var[str]


class BreadcrumbItem(ChakraComponent):
    """Individual breadcrumb element containing a link and a divider."""

    tag = "BreadcrumbItem"

    # Is the current page of the breadcrumb.
    is_current_page: Var[bool]

    # Is the last child of the breadcrumb.
    is_last_child: Var[bool]

    # The visual separator between each breadcrumb item
    separator: Var[str]

    # The left and right margin applied to the separator
    spacing: Var[str]

    # The href of the item.
    href: Var[str]


class BreadcrumbSeparator(ChakraComponent):
    """The visual separator between each breadcrumb."""

    tag = "BreadcrumbSeparator"


class BreadcrumbLink(ChakraComponent):
    """The breadcrumb link."""

    tag = "BreadcrumbLink"

    # Is the current page of the breadcrumb.
    is_current_page: Var[bool]
