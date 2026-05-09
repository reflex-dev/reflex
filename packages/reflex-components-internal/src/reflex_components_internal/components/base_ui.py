"""Base UI component."""

# Based on https://base-ui.com/

from reflex_components_internal.components.component import CoreComponent

PACKAGE_NAME = "@base-ui/react"
PACKAGE_VERSION = "1.4.1"


class BaseUIComponent(CoreComponent):
    """Base UI component."""

    lib_dependencies: list[str] = [f"{PACKAGE_NAME}@{PACKAGE_VERSION}"]
