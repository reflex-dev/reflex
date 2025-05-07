"""A class that holds props to be passed or applied to a component."""

from __future__ import annotations

from pydantic import ValidationError

from reflex.base import Base
from reflex.utils import format
from reflex.utils.exceptions import InvalidPropValueError
from reflex.vars.object import LiteralObjectVar


class PropsBase(Base):
    """Base for a class containing props that can be serialized as a JS object."""

    def json(self) -> str:
        """Convert the object to a json-like string.

        Vars will be unwrapped so they can represent actual JS var names and functions.

        Keys will be converted to camelCase.

        Returns:
            The object as a Javascript Object literal.
        """
        return LiteralObjectVar.create(
            {format.to_camel_case(key): value for key, value in self.dict().items()}
        ).json()

    def dict(self, *args, **kwargs):
        """Convert the object to a dictionary.

        Keys will be converted to camelCase.

        Args:
            *args: Arguments to pass to the parent class.
            **kwargs: Keyword arguments to pass to the parent class.

        Returns:
            The object as a dictionary.
        """
        return {
            format.to_camel_case(key): value
            for key, value in super().dict(*args, **kwargs).items()
        }


class NoExtrasAllowedProps(Base):
    """A class that holds props to be passed or applied to a component with no extra props allowed."""

    def __init__(self, component_name: str | None = None, **kwargs):
        """Initialize the props.

        Args:
            component_name: The custom name of the component.
            kwargs: Kwargs to initialize the props.

        Raises:
            InvalidPropValueError: If invalid props are passed on instantiation.
        """
        component_name = component_name or type(self).__name__
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            invalid_fields = ", ".join([error["loc"][0] for error in e.errors()])  # pyright: ignore [reportCallIssue, reportArgumentType]
            supported_props_str = ", ".join(f'"{field}"' for field in self.get_fields())
            raise InvalidPropValueError(
                f"Invalid prop(s) {invalid_fields} for {component_name!r}. Supported props are {supported_props_str}"
            ) from None

    class Config:  # pyright: ignore [reportIncompatibleVariableOverride]
        """Pydantic config."""

        arbitrary_types_allowed = True
        use_enum_values = True
        extra = "forbid"
