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


def test_bundle_registrations_survive_fork_and_respect_explicit_reset():
    """Forked contexts retain app bundles, and resetting one clears them only there."""
    with RegistrationContext() as original:
        dynamic.bundle_library("app-library@1.0.0")
        with original.fork() as forked:
            dynamic._reset_bundled_libraries_for_compile()
            assert "app-library" in forked.bundled_libraries
            dynamic.reset_bundled_libraries()
            dynamic._reset_bundled_libraries_for_compile()
            assert forked.bundled_libraries == _default_bundled_libraries()

        dynamic._reset_bundled_libraries_for_compile()
        assert "app-library" in original.bundled_libraries


def test_repeated_app_bundle_registrations_do_not_accumulate():
    """Registration from reevaluated page functions does not grow the bundle registry."""
    with RegistrationContext() as context:
        for _ in range(3):
            dynamic._reset_bundled_libraries_for_compile()
            dynamic.bundle_library("app-library@1.0.0")
            dynamic.bundle_library("app-library")
            assert context.bundled_libraries.count("app-library") == 1


@pytest.mark.parametrize("library", ["app-library", "react"])
def test_bundle_registrations_are_unique_across_scopes(library: str):
    """Deduplicate compiler and app registrations, including default libraries.

    Args:
        library: A default or application-provided library.
    """
    with RegistrationContext() as context:
        dynamic._bundle_library(library)
        dynamic._bundle_library(f"{library}@1.0.0")
        dynamic.bundle_library(library)
        assert context.bundled_libraries.count(library) == 1
        dynamic._reset_bundled_libraries_for_compile()
        assert context.bundled_libraries.count(library) == 1


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
