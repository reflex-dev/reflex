"""How a runner knows a page of the harness app is hydrated.

React gives a server-rendered element its fiber while it still renders, before
anything is committed: Emotion has not moved its style tags yet, and no effect
has attached a behaviour. An effect of the first render runs only once the
root has committed, so every page ends in a marker whose effect flags the
document, and the runners wait for the flag.
"""

from __future__ import annotations

from reflex_base.components.component import Component
from reflex_base.utils.imports import ImportDict

# The attribute of the document element the marker sets.
ATTRIBUTE = "data-parity-hydrated"

# A JavaScript expression that is true once the page is hydrated.
IS_HYDRATED = f'document.documentElement.hasAttribute("{ATTRIBUTE}")'

# Elements that render nothing, which a library may put beside a component.
NOT_RENDERED = ("style", "script", "link", "template")


class HydrationMarker(Component):
    """Flag the document once the page it is on has hydrated."""

    tag = "Fragment"
    library = "react"

    def add_imports(self) -> ImportDict:
        """Import the hook the marker runs.

        Returns:
            The import.
        """
        return {"react": "useEffect"}

    def add_hooks(self) -> list[str]:
        """Set the flag in an effect, which runs after the root commits.

        Returns:
            The hook.
        """
        flag = f'document.documentElement.setAttribute("{ATTRIBUTE}", "")'
        return [f"useEffect(() => {{ {flag}; }}, []);"]
