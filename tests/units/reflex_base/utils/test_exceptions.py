"""Tests for reflex_base.utils.exceptions."""

from unittest import mock

from reflex_base.utils.exceptions import ReflexError


def test_base_var_shadows_inherited_var_error_is_deprecated():
    """Importing the removed shadowing error still works, with a deprecation warning."""
    with mock.patch("reflex_base.utils.console.deprecate") as deprecate:
        from reflex.utils.exceptions import BaseVarShadowsInheritedVarError

    assert issubclass(BaseVarShadowsInheritedVarError, ReflexError)
    assert issubclass(BaseVarShadowsInheritedVarError, NameError)
    deprecate.assert_called_once_with(
        feature_name="BaseVarShadowsInheritedVarError",
        reason="Nothing raises it: a substate may redeclare an inherited var.",
        deprecation_version="0.11.0",
        removal_version="1.0",
    )
