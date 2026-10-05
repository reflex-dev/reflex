"""Tests for version-dependent annotation compatibility."""

import dataclasses
import sys
from collections.abc import Callable
from typing import Any, get_args, get_type_hints

import pytest
from reflex_base.components.component import ComponentField
from reflex_base.components.component import field as component_field
from reflex_base.components.field import BaseField
from reflex_base.components.props import PropsField, props_field
from reflex_base.vars.base import Field, field


@pytest.mark.parametrize(
    "factory",
    [
        BaseField.__init__,
        ComponentField.__init__,
        component_field,
        PropsField.__init__,
        props_field,
        Field.__init__,
        field,
    ],
)
def test_field_default_annotation(factory: Callable[..., Any]) -> None:
    """Field default annotations use the version-appropriate missing sentinel.

    Args:
        factory: A field constructor or factory to inspect.
    """
    if sys.version_info >= (3, 15):
        missing = dataclasses.MISSING
    else:
        missing = dataclasses._MISSING_TYPE
    assert missing in get_args(get_type_hints(factory)["default"])
