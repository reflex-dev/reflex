"""A React tag."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union

from reflex.base import Base
from reflex.event import EventChain
from reflex.utils import format, types
from reflex.vars import Var


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

    def format_props(self) -> List:
        """Format the tag's props.

        Returns:
            The formatted props list.
        """
        return format.format_props(*self.special_props, **self.props)

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
            prop_name = format.to_camel_case(name)
            if prop_name in self.props:
                del self.props[prop_name]
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
