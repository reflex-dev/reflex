"""Define the base Reflex class."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Type

import pydantic.v1.main as pydantic_main
from pydantic.v1 import BaseModel
from pydantic.v1.fields import ModelField


def validate_field_name(bases: list[Type["BaseModel"]], field_name: str) -> None:
    """Ensure that the field's name does not shadow an existing attribute of the model.

    Args:
        bases: List of base models to check for shadowed attrs.
        field_name: name of attribute

    Raises:
        VarNameError: If state var field shadows another in its parent state
    """
    from reflex.utils.exceptions import VarNameError

    # can't use reflex.config.environment here cause of circular import
    reload = os.getenv("__RELOAD_CONFIG", "").lower() == "true"
    base = None
    try:
        for base in bases:
            if not reload and getattr(base, field_name, None):
                pass
    except TypeError as te:
        raise VarNameError(
            f'State var "{field_name}" in {base} has been shadowed by a substate var; '
            f'use a different field name instead".'
        ) from te


# monkeypatch pydantic validate_field_name method to skip validating
# shadowed state vars when reloading app via utils.prerequisites.get_app(reload=True)
pydantic_main.validate_field_name = validate_field_name  # pyright: ignore [reportPrivateImportUsage]

if TYPE_CHECKING:
    from reflex.vars import Var


class Base(BaseModel):
    """The base class subclassed by all Reflex classes.

    This class wraps Pydantic and provides common methods such as
    serialization and setting fields.

    Any data structure that needs to be transferred between the
    frontend and backend should subclass this class.
    """

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        use_enum_values = True
        extra = "allow"

    def json(self) -> str:
        """Convert the object to a json string.

        Returns:
            The object as a json string.
        """
        from reflex.utils.serializers import serialize

        return self.__config__.json_dumps(
            self.dict(),
            default=serialize,
        )

    def set(self, **kwargs: Any):
        """Set multiple fields and return the object.

        Args:
            **kwargs: The fields and values to set.

        Returns:
            The object with the fields set.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    @classmethod
    def get_fields(cls) -> dict[str, ModelField]:
        """Get the fields of the object.

        Returns:
            The fields of the object.
        """
        return cls.__fields__

    @classmethod
    def add_field(cls, var: Var, default_value: Any):
        """Add a pydantic field after class definition.

        Used by State.add_var() to correctly handle the new variable.

        Args:
            var: The variable to add a pydantic field for.
            default_value: The default value of the field
        """
        var_name = var._var_field_name
        new_field = ModelField.infer(
            name=var_name,
            value=default_value,
            annotation=var._var_type,
            class_validators=None,
            config=cls.__config__,
        )
        cls.__fields__.update({var_name: new_field})

    def get_value(self, key: str) -> Any:
        """Get the value of a field.

        Args:
            key: The key of the field.

        Returns:
            The value of the field.
        """
        if isinstance(key, str):
            # Seems like this function signature was wrong all along?
            # If the user wants a field that we know of, get it and pass it off to _get_value
            return getattr(self, key)
        return key
