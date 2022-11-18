"""A React tag."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Union

from plotly.graph_objects import Figure
from plotly.io import to_json

from pynecone import utils
from pynecone.base import Base
from pynecone.event import EventChain
from pynecone.var import Var


class Tag(Base):
    """A React tag."""

    # The name of the tag.
    name: str = ""

    # The props of the tag.
    props: Dict[str, Any] = {}

    # The inner contents of the tag.
    contents: str = ""

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
    def format_attr_value(
        value: Union[Var, EventChain, Dict[str, Var], str],
    ) -> Union[int, float, str]:
        """Format an attribute value.

        Args:
            value: The value of the attribute

        Returns:
            The formatted value to display within the tag.
        """

        def format_fn(value):
            args = ",".join([":".join((name, val)) for name, val in value.args])
            return f"E(\"{utils.to_snake_case(value.handler.fn.__qualname__)}\", {utils.wrap(args, '{')})"

        # Handle var attributes.
        if isinstance(value, Var):
            if not value.is_local or value.is_string:
                return str(value)
            if issubclass(value.type_, str):
                value = json.dumps(value.full_name)
                value = re.sub('"{', "", value)
                value = re.sub('}"', "", value)
                value = re.sub('"`', '{"', value)
                value = re.sub('`"', '"}', value)
                return value
            value = value.full_name

        # Handle events.
        elif isinstance(value, EventChain):
            local_args = ",".join(value.events[0].local_args)
            fns = ",".join([format_fn(event) for event in value.events])
            value = f"({local_args}) => Event([{fns}])"

        # Handle other types.
        elif isinstance(value, str):
            if utils.is_wrapped(value, "{"):
                return value
            return json.dumps(value)

        elif isinstance(value, Figure):
            value = json.loads(to_json(value))["data"]

        # For dictionaries, convert any properties to strings.
        else:
            if isinstance(value, dict):
                value = json.dumps(
                    {
                        key: str(val) if isinstance(val, Var) else val
                        for key, val in value.items()
                    }
                )
            else:
                value = json.dumps(value)

            value = re.sub('"{', "", value)
            value = re.sub('}"', "", value)
            value = re.sub('"`', '{"', value)
            value = re.sub('`"', '"}', value)

        # Wrap the variable in braces.
        assert isinstance(value, str), "The value must be a string."
        return utils.wrap(value, "{", check_first=False)

    def format_props(self) -> str:
        """Format a dictionary of attributes.

        Returns:
            The formatted attributes.
        """
        # If there are no attributes, return an empty string.
        if len(self.props) == 0:
            return ""

        # Get the string representation of all the attributes joined.
        # We need a space at the beginning for formatting.
        return os.linesep.join(
            f"{name}={self.format_attr_value(value)}"
            for name, value in self.props.items()
            if value is not None
        )

    def __str__(self) -> str:
        """Render the tag as a React string.

        Returns:
            The React code to render the tag.
        """
        # Get the tag attributes.
        props_str = self.format_props()
        if len(props_str) > 0:
            props_str = " " + props_str

        if len(self.contents) == 0:
            # If there is no inner content, we don't need a closing tag.
            tag_str = utils.wrap(f"{self.name}{props_str}/", "<")
        else:
            # Otherwise wrap it in opening and closing tags.
            open = utils.wrap(f"{self.name}{props_str}", "<")
            close = utils.wrap(f"/{self.name}", "<")
            tag_str = utils.wrap(self.contents, open, close)

        return tag_str

    def add_props(self, **kwargs: Optional[Any]) -> Tag:
        """Add attributes to the tag.

        Args:
            **kwargs: The attributes to add.

        Returns:
            The tag with the attributes added.
        """
        self.props.update(
            {
                utils.to_camel_case(name): attr
                if utils._isinstance(attr, Union[EventChain, dict])
                else Var.create(attr)
                for name, attr in kwargs.items()
                if self.is_valid_attr(attr)
            }
        )
        return self

    def remove_props(self, *args: str) -> Tag:
        """Remove attributes from the tag.

        Args:
            *args: The attributes to remove.

        Returns:
            The tag with the attributes removed.
        """
        for name in args:
            if name in self.props:
                del self.props[name]
        return self

    @staticmethod
    def is_valid_attr(attr: Optional[Var]) -> bool:
        """Check if the attr is valid.

        Args:
            attr: The value to check.

        Returns:
            Whether the value is valid.
        """
        return attr is not None and not (isinstance(attr, dict) and len(attr) == 0)
