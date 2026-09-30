"""Field defaults retain their value types when the missing sentinel is excluded."""

from dataclasses import MISSING

from reflex_base.components.field import BaseField
from reflex_base.utils.compat import MISSING_TYPE
from reflex_base.vars.base import Field, field
from typing_extensions import assert_type


def check_missing_default(value: int | MISSING_TYPE = MISSING) -> None:
    """Check that excluding MISSING narrows a field default to its value type.

    Args:
        value: A field default or the missing sentinel.
    """
    if value is not MISSING:
        assert_type(value, int)
        assert_type(BaseField(default=value).default_value(), int)
        assert_type(field(default=value), Field[int])
        assert_type(field(default=value, is_var=False), int)
