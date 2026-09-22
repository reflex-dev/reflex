"""Component with ClassVar, private attrs, and excluded props.

This module tests:
- ClassVar annotations are preserved (not turned into create() kwargs)
- Private annotated attributes (_foo) are removed from stubs
- EXCLUDED_PROPS (like tag, library, etc.) are not in create()
- Private methods are removed
- Non-annotated assignments inside Component classes are removed
- AnnAssign with value is blanked (value set to None)
"""

from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var


class StrictComponent(Component):
    """A component with ClassVar, private, and excluded props."""

    _internal_counter: int = 0

    _hidden_state: ClassVar[dict[str, Any]] = {}

    tag: str | None = "div"

    library: str | None = "some-lib"

    # The valid children for this component.
    _valid_children: ClassVar[list[str]] = ["ChildA", "ChildB"]

    # The memoization mode.
    _memoization_mode: ClassVar[Any] = None  # ty:ignore[invalid-attribute-override]

    # A public prop that should appear in create().
    visible_prop: Var[str] = field(doc="A prop visible in the stub.")

    # Another public prop.
    size: Var[int] = field(doc="The size of the component.")

    some_constant = "not_a_prop"

    def _internal_helper(self) -> None:
        """Private method, should be removed."""

    def render_item(self) -> str:
        """Public method, body should be blanked.

        Returns:
            The rendered item.
        """
        return f"<div>{self.visible_prop}</div>"
