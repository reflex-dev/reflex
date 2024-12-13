import pytest

from reflex.components.props import NoExtrasAllowedProps
from reflex.utils.exceptions import InvalidPropValueError

try:
    from pydantic.v1 import ValidationError
except ModuleNotFoundError:
    from pydantic import ValidationError


class PropA(NoExtrasAllowedProps):
    """Base prop class."""

    foo: str
    bar: str


class PropB(NoExtrasAllowedProps):
    """Prop class with nested props."""

    foobar: str
    foobaz: PropA


@pytest.mark.parametrize(
    "props_class, kwargs, should_raise",
    [
        (PropA, {"foo": "value", "bar": "another_value"}, False),
        (PropA, {"fooz": "value", "bar": "another_value"}, True),
        (
            PropB,
            {
                "foobaz": {"foo": "value", "bar": "another_value"},
                "foobar": "foo_bar_value",
            },
            False,
        ),
        (
            PropB,
            {
                "fooba": {"foo": "value", "bar": "another_value"},
                "foobar": "foo_bar_value",
            },
            True,
        ),
        (
            PropB,
            {
                "foobaz": {"foobar": "value", "bar": "another_value"},
                "foobar": "foo_bar_value",
            },
            True,
        ),
    ],
)
def test_no_extras_allowed_props(props_class, kwargs, should_raise):
    if should_raise:
        with pytest.raises((ValidationError, InvalidPropValueError)):
            props_class(**kwargs)
    else:
        props_instance = props_class(**kwargs)
        assert isinstance(props_instance, props_class)
