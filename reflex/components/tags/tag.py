"""A React tag."""

from __future__ import annotations

import dataclasses
from typing import Any, List, Mapping, Sequence

from reflex.event import EventChain
from reflex.utils import format
from reflex.vars.base import LiteralVar, Var


def render_prop(value: Any) -> Any:
    """Render the prop.

    Args:
        value: The value to render.

    Returns:
        The rendered value.
    """
    from reflex.components.component import BaseComponent

    if isinstance(value, BaseComponent):
        return value.render()
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [render_prop(v) for v in value]
    if callable(value) and not isinstance(value, Var):
        return None
    return value


@dataclasses.dataclass()
class Tag:
    """A React tag."""

    # The name of the tag.
    name: str = ""

    # The props of the tag.
    props: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The inner contents of the tag.
    contents: str = ""

    # Special props that aren't key value pairs.
    special_props: list[Var] = dataclasses.field(default_factory=list)

    # The children components.
    children: list[Any] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        """Post initialize the tag."""
        object.__setattr__(
            self,
            "props",
            {name: LiteralVar.create(value) for name, value in self.props.items()},
        )

    def format_props(self) -> List:
        """Format the tag's props.

        Returns:
            The formatted props list.
        """
        return format.format_props(*self.special_props, **self.props)

    def set(self, **kwargs: Any):
        """Set the tag's fields.

        Args:
            **kwargs: The fields to set.

        Returns:
            The tag with the fields
        """
        for name, value in kwargs.items():
            setattr(self, name, value)

        return self

    def __iter__(self):
        """Iterate over the tag's fields.

        Yields:
            tuple[str, Any]: The field name and value.
        """
        for field in dataclasses.fields(self):
            rendered_value = render_prop(getattr(self, field.name))
            if rendered_value is not None:
                yield field.name, rendered_value

    def add_props(self, **kwargs: Any | None) -> Tag:
        """Add props to the tag.

        Args:
            **kwargs: The props to add.

        Returns:
            The tag with the props added.
        """
        self.props.update(
            {
                format.to_camel_case(name, treat_hyphens_as_underscores=False): (
                    prop
                    if isinstance(prop, (EventChain, Mapping))
                    else LiteralVar.create(prop)
                )
                for name, prop in kwargs.items()
                if self.is_valid_prop(prop)
            }
        )
        return self

    def remove_props(self, *args: str) -> Tag:
        """Remove props from the tag.

        Args:
            *args: The props to remove.

        Returns:
            The tag with the props removed.
        """
        for name in args:
            prop_name = format.to_camel_case(name)
            if prop_name in self.props:
                del self.props[prop_name]
        return self

    @staticmethod
    def is_valid_prop(prop: Var | None) -> bool:
        """Check if the prop is valid.

        Args:
            prop: The prop to check.

        Returns:
            Whether the prop is valid.
        """
        return prop is not None and not (isinstance(prop, dict) and len(prop) == 0)
