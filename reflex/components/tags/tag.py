"""A React tag."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from plotly.graph_objects import Figure
from plotly.io import to_json

from reflex.base import Base
from reflex.event import EVENT_ARG, EventChain
from reflex.utils import format, types
from reflex.vars import Var

if TYPE_CHECKING:
    from reflex.components.component import ComponentStyle


class Tag(Base):
    """A React tag."""

    # The name of the tag.
    name: str = ""

    # The props of the tag.
    props: Dict[str, Any] = {}

    # The inner contents of the tag.
    contents: str = ""

    # Args to pass to the tag.
    args: Optional[Tuple[str, ...]] = None

    # Special props that aren't key value pairs.
    special_props: Set[Var] = set()

    # The children components.
    children: List[Any] = []

    def __init__(self, *args, **kwargs):
        """Initialize the tag.

        Args:
            *args: Args to initialize the tag.
            **kwargs: Kwargs to initialize the tag.
        """
        # Convert any props to vars.
        if "props" in kwargs:
            kwargs["props"] = {
                name: Var.create(value) for name, value in kwargs["props"].items()
            }
        super().__init__(*args, **kwargs)

    @staticmethod
    def format_prop(
        prop: Union[Var, EventChain, ComponentStyle, str],
    ) -> Union[int, float, str]:
        """Format a prop.

        Args:
            prop: The prop to format.

        Returns:
            The formatted prop to display within a tag.

        Raises:
            TypeError: If the prop is not a valid type.
        """
        # Handle var props.
        if isinstance(prop, Var):
            if not prop.is_local or prop.is_string:
                return str(prop)
            if types._issubclass(prop.type_, str):
                return format.json_dumps(prop.full_name)
            prop = prop.full_name

        # Handle event props.
        elif isinstance(prop, EventChain):
            if prop.full_control:
                # Full control component events.
                event = format.format_full_control_event(prop)
            else:
                # All other events.
                chain = ",".join([format.format_event(event) for event in prop.events])
                event = f"Event([{chain}], {EVENT_ARG})"
            prop = f"{EVENT_ARG} => {event}"

        # Handle other types.
        elif isinstance(prop, str):
            if format.is_wrapped(prop, "{"):
                return prop
            return format.json_dumps(prop)

        elif isinstance(prop, Figure):
            prop = json.loads(to_json(prop))["data"]  # type: ignore

        # For dictionaries, convert any properties to strings.
        elif isinstance(prop, dict):
            prop = format.format_dict(prop)

        else:
            # Dump the prop as JSON.
            try:
                prop = format.json_dumps(prop)
            except TypeError as e:
                raise TypeError(
                    f"Could not format prop: {prop} of type {type(prop)}"
                ) from e

        # Wrap the variable in braces.
        assert isinstance(prop, str), "The prop must be a string."
        return format.wrap(prop, "{", check_first=False)

    def format_props(self) -> List:
        """Format the tag's props.

        Returns:
            The formatted props list.
        """
        # If there are no props, return an empty string.
        if len(self.props) == 0:
            return []

        # Format all the props.
        return [
            f"{name}={self.format_prop(prop)}"
            for name, prop in sorted(self.props.items())
            if prop is not None
        ] + [str(prop) for prop in self.special_props]

    def add_props(self, **kwargs: Optional[Any]) -> Tag:
        """Add props to the tag.

        Args:
            **kwargs: The props to add.

        Returns:
            The tag with the props added.
        """
        self.props.update(
            {
                format.to_camel_case(name): prop
                if types._isinstance(prop, Union[EventChain, dict])
                else Var.create(prop)
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
            if name in self.props:
                del self.props[name]
        return self

    @staticmethod
    def is_valid_prop(prop: Optional[Var]) -> bool:
        """Check if the prop is valid.

        Args:
            prop: The prop to check.

        Returns:
            Whether the prop is valid.
        """
        return prop is not None and not (isinstance(prop, dict) and len(prop) == 0)
