"""Tests for the compatibility shims in reflex_base.components.dynamic."""

import importlib

import pytest
from reflex_base.components import dynamic
from reflex_base.registry import RegistrationContext, _default_bundled_libraries

from reflex.components import dynamic as reflex_dynamic


def test_bundled_libraries_shim_returns_active_context_list():
    """The module-level `bundled_libraries` resolves against the active context."""
    with RegistrationContext() as ctx:
        assert dynamic.bundled_libraries is ctx.bundled_libraries
        dynamic.bundle_library("some-shimmed-lib")
        assert "some-shimmed-lib" in dynamic.bundled_libraries

    with RegistrationContext():
        assert "some-shimmed-lib" not in dynamic.bundled_libraries


def test_bundled_libraries_shim_via_reflex_namespace():
    """reflex-enterprise reads the shim off `reflex.components.dynamic`."""
    with RegistrationContext() as ctx:
        assert set(reflex_dynamic.bundled_libraries) == set(ctx.bundled_libraries)


def test_default_bundled_libraries_shim():
    """The `DEFAULT_BUNDLED_LIBRARIES` shim returns the default library list."""
    assert _default_bundled_libraries() == dynamic.DEFAULT_BUNDLED_LIBRARIES


def test_bundled_libraries_shim_warns(mocker):
    """Reading a relocated global emits a deprecation warning."""
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")

    with RegistrationContext():
        _ = dynamic.bundled_libraries
    deprecate.assert_called_once()
    assert (
        deprecate.call_args.kwargs["feature_name"]
        == "reflex_base.components.dynamic.bundled_libraries"
    )


@pytest.mark.parametrize("module_name", ["reflex_base", "reflex"])
def test_unknown_attribute_raises(module_name: str):
    """Unknown attributes still raise AttributeError naming the module."""
    module = importlib.import_module(f"{module_name}.components.dynamic")
    with pytest.raises(AttributeError, match=f"{module.__name__!r}"):
        _ = module.definitely_not_an_attribute
