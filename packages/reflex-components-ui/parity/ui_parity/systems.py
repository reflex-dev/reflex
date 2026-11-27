"""The two component systems the harness compares."""

from __future__ import annotations

import dataclasses
import importlib
from types import ModuleType


@dataclasses.dataclass(frozen=True)
class System:
    """A namespace of components.

    Attributes:
        name: The name an app refers to it by.
        role: What it is to a comparison: the reference or the candidate.
        slug: Its name in a route.
        module: The module the namespace is.
    """

    name: str
    role: str
    slug: str
    module: str

    @property
    def namespace(self) -> ModuleType:
        """The namespace components are created from.

        Returns:
            ``rx`` or ``rx.ui``.
        """
        return importlib.import_module(self.module)


# Radix Themes, which a component must look and behave like.
REFERENCE = System(name="rx", role="reference", slug="rx", module="reflex")
# The compiled components.
CANDIDATE = System(
    name="rx.ui", role="candidate", slug="ui", module="reflex_components_ui"
)
SYSTEMS = (REFERENCE, CANDIDATE)
