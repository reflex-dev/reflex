"""Base UI component."""

# Based on https://base-ui.com/

from reflex_ui.components.component import CoreComponent

PACKAGE_NAME = "@base-ui/react"
PACKAGE_VERSION = "1.3.0"


class BaseUIComponent(CoreComponent):
    """Base UI component."""

    lib_dependencies: list[str] = [f"{PACKAGE_NAME}@{PACKAGE_VERSION}"]
