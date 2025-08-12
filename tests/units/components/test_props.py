import pytest
from pydantic.v1 import ValidationError

from reflex.components.props import NoExtrasAllowedProps, PropsBase
from reflex.utils.exceptions import InvalidPropValueError


class PropA(NoExtrasAllowedProps):
    """Base prop class."""

    foo: str
    bar: str


class PropB(NoExtrasAllowedProps):
    """Prop class with nested props."""

    foobar: str
    foobaz: PropA


@pytest.mark.parametrize(
    ("props_class", "kwargs", "should_raise"),
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


# Test class definitions - reused across tests
class MixedCaseProps(PropsBase):
    """Test props with mixed naming conventions."""

    # Single word (no case conversion needed)
    name: str
    # Already camelCase (should stay unchanged)
    fontSize: int = 12
    # snake_case (should convert to camelCase)
    max_length: int = 100
    is_active: bool = True


class NestedProps(PropsBase):
    """Test props for nested PropsBase testing."""

    user_name: str
    max_count: int = 10


class ParentProps(PropsBase):
    """Test props containing nested PropsBase objects."""

    title: str
    nested_config: NestedProps
    is_enabled: bool = True


class OptionalFieldProps(PropsBase):
    """Test props with optional fields to test omission behavior."""

    required_field: str
    optional_snake_case: str | None = None
    optionalCamelCase: int | None = None


@pytest.mark.parametrize(
    ("props_class", "props_kwargs", "expected_dict"),
    [
        # Test single word + snake_case conversion
        (
            MixedCaseProps,
            {"name": "test", "max_length": 50},
            {"name": "test", "fontSize": 12, "maxLength": 50, "isActive": True},
        ),
        # Test existing camelCase stays unchanged + snake_case converts
        (
            MixedCaseProps,
            {"name": "demo", "fontSize": 16, "is_active": False},
            {"name": "demo", "fontSize": 16, "maxLength": 100, "isActive": False},
        ),
        # Test all different case types together
        (
            MixedCaseProps,
            {"name": "full", "fontSize": 20, "max_length": 200, "is_active": False},
            {"name": "full", "fontSize": 20, "maxLength": 200, "isActive": False},
        ),
        # Test nested PropsBase conversion
        (
            ParentProps,
            {
                "title": "parent",
                "nested_config": NestedProps(user_name="nested_user", max_count=5),
            },
            {
                "title": "parent",
                "nestedConfig": {"userName": "nested_user", "maxCount": 5},
                "isEnabled": True,
            },
        ),
        # Test nested with different values
        (
            ParentProps,
            {
                "title": "test",
                "nested_config": NestedProps(user_name="test_user"),
                "is_enabled": False,
            },
            {
                "title": "test",
                "nestedConfig": {"userName": "test_user", "maxCount": 10},
                "isEnabled": False,
            },
        ),
        # Test omitted optional fields appear with None values
        (
            OptionalFieldProps,
            {"required_field": "present"},
            {
                "requiredField": "present",
            },
        ),
        # Test explicit None values for optional fields
        (
            OptionalFieldProps,
            {
                "required_field": "test",
                "optional_snake_case": None,
                "optionalCamelCase": 42,
            },
            {
                "requiredField": "test",
                "optionalCamelCase": 42,
            },
        ),
    ],
)
def test_props_base_dict_conversion(props_class, props_kwargs, expected_dict):
    """Test that dict() handles different naming conventions correctly for both simple and nested props.

    Args:
        props_class: The PropsBase class to test.
        props_kwargs: The keyword arguments to pass to the class constructor.
        expected_dict: The expected dictionary output with camelCase keys.
    """
    props = props_class(**props_kwargs)
    result = props.dict()
    assert result == expected_dict
