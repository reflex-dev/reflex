"""A React tag."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

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


@dataclasses.dataclass(frozen=True)
class Tag:
    """A React tag."""

    # The name of the tag.
    name: str = ""

    # The props of the tag.
    props: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    # The inner contents of the tag.
    contents: str = ""

    # Special props that aren't key value pairs.
    special_props: Sequence[Var] = dataclasses.field(default_factory=list)

    # The children components.
    children: Sequence[Any] = dataclasses.field(default_factory=list)

    def format_props(self) -> list:
        """Format the tag's props.

        Returns:
            The formatted props list.
        """
        return format.format_props(*self.special_props, **self.props)

    def set(self, **kwargs: Any):
        """Return a new tag with the given fields set.

        Args:
            **kwargs: The fields to set.

        Returns:
            The tag with the fields set.
        """
        return dataclasses.replace(self, **kwargs)

    def __iter__(self):
        """Iterate over the tag's fields.

        Yields:
            tuple[str, Any]: The field name and value.
        """
        for field in dataclasses.fields(self):
            if field.name == "props":
                yield "props", self.format_props()
            elif field.name != "special_props":
                rendered_value = render_prop(getattr(self, field.name))
                if rendered_value is not None:
                    yield field.name, rendered_value

    def add_props(self, **kwargs: Any | None) -> Tag:
        """Return a new tag with the given props added.

        Args:
            **kwargs: The props to add.

        Returns:
            The tag with the props added.
        """
        return dataclasses.replace(
            self,
            props={
                **self.props,
                **{
                    format.to_camel_case(name, treat_hyphens_as_underscores=False): (
                        prop
                        if isinstance(prop, (EventChain, Mapping))
                        else LiteralVar.create(prop)
                    )
                    for name, prop in kwargs.items()
                    if self.is_valid_prop(prop)
                },
            },
        )

    def remove_props(self, *args: str) -> Tag:
        """Return a new tag with the given props removed.

        Args:
            *args: The names of the props to remove.

        Returns:
            The tag with the props removed.
        """
        formatted_args = [format.to_camel_case(arg) for arg in args]
        return dataclasses.replace(
            self,
            props={
                name: value
                for name, value in self.props.items()
                if name not in formatted_args
            },
        )

    @staticmethod
    def is_valid_prop(prop: Var | None) -> bool:
        """Check if the prop is valid.

        Args:
            prop: The prop to check.

        Returns:
            Whether the prop is valid.
        """
        return prop is not None and not (isinstance(prop, dict) and len(prop) == 0)
