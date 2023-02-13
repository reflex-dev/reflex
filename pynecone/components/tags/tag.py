"""A React tag."""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from plotly.graph_objects import Figure
from plotly.io import to_json

from pynecone import utils
from pynecone.base import Base
from pynecone.event import EventChain
from pynecone.var import Var

if TYPE_CHECKING:
    from pynecone.components.component import ComponentStyle


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
    def format_prop(
        prop: Union[Var, EventChain, ComponentStyle, str],
    ) -> Union[int, float, str]:
        """Format a prop.

        Args:
            prop: The prop to format.

        Returns:
            The formatted prop to display within a tag.
        """
        # Handle var props.
        if isinstance(prop, Var):
            if not prop.is_local or prop.is_string:
                return str(prop)
            if issubclass(prop.type_, str):
                return json.dumps(prop.full_name)
            prop = prop.full_name

        # Handle event props.
        elif isinstance(prop, EventChain):
            local_args = ",".join(prop.events[0].local_args)
            events = ",".join([utils.format_event(event) for event in prop.events])
            prop = f"({local_args}) => Event([{events}])"

        # Handle other types.
        elif isinstance(prop, str):
            if utils.is_wrapped(prop, "{"):
                return prop
            return json.dumps(prop)

        elif isinstance(prop, Figure):
            prop = json.loads(to_json(prop))["data"]  # type: ignore

        # For dictionaries, convert any properties to strings.
        else:
            if isinstance(prop, dict):
                # Convert any var keys to strings.
                prop = {
                    key: str(val) if isinstance(val, Var) else val
                    for key, val in prop.items()
                }

            # Dump the prop as JSON.
            prop = json.dumps(prop)

            # This substitution is necessary to unwrap var values.
            prop = re.sub('"{', "", prop)
            prop = re.sub('}"', "", prop)

        # Wrap the variable in braces.
        assert isinstance(prop, str), "The prop must be a string."
        return utils.wrap(prop, "{", check_first=False)

    def format_props(self) -> str:
        """Format the tag's props.

        Returns:
            The formatted props.
        """
        # If there are no props, return an empty string.
        if len(self.props) == 0:
            return ""

        # Format all the props.
        return os.linesep.join(
            f"{name}={self.format_prop(prop)}"
            for name, prop in self.props.items()
            if prop is not None
        )

    def __str__(self) -> str:
        """Render the tag as a React string.

        Returns:
            The React code to render the tag.
        """
        # Get the tag props.
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
        """Add props to the tag.

        Args:
            **kwargs: The props to add.

        Returns:
            The tag with the props added.
        """
        self.props.update(
            {
                utils.to_camel_case(name): prop
                if utils._isinstance(prop, Union[EventChain, dict])
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
