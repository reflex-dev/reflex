"""Tests for the compatibility shims in reflex_base.components.dynamic."""

import importlib
from typing import Any

import pytest
from reflex_base.components import dynamic
from reflex_base.components.component import Component
from reflex_base.registry import RegistrationContext, _default_bundled_libraries
from reflex_base.utils.exceptions import DynamicComponentMissingLibraryError
from reflex_base.utils.imports import ImportVar, ParsedImportDict

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


@pytest.mark.parametrize("library", [None, "unused-library@1.0.0"])
def test_component_bundles_its_rendered_imports(library: str | None):
    """Bundle the declared imports even when they differ from component.library.

    Args:
        library: The component's absent or overridden nominal library.
    """

    class SpecializedComponent(Component):
        """A component that replaces its library imports."""

        tag = "Widget"

        def _get_imports(self) -> ParsedImportDict:
            """Declare the modules used by the specialized component.

            Returns:
                Rendered modules, an install-only dependency, and a stylesheet.
            """
            return {
                "@test/library@1.0.0": [
                    ImportVar("Widget", package_path="/widget.mjs"),
                    ImportVar("helper", package_path="/widget.mjs"),
                ],
                "test-helper@1.0.0": [ImportVar("helper", package_path="")],
                "test-root@1.0.0": [ImportVar("Root")],
                "install-only": [ImportVar(None, render=False)],
                "": [ImportVar("theme.css")],
            }

    with RegistrationContext() as context:
        dynamic.bundle_library(SpecializedComponent.create(library=library))
        dynamic._reset_bundled_libraries_for_compile()
        assert context.bundled_libraries == [
            *_default_bundled_libraries(),
            "@test/library/widget.mjs",
            "test-helper",
            "test-root",
        ]


def test_component_without_imports_cannot_be_bundled():
    """Report components that have no libraries to register."""
    with pytest.raises(DynamicComponentMissingLibraryError):
        dynamic.bundle_library(Component.create())


@pytest.mark.parametrize(
    "component",
    [None, 42, {}, [], object(), Component, Component.create],
    ids=["none", "integer", "dict", "list", "object", "component-class", "factory"],
)
def test_bundle_library_rejects_invalid_inputs(component: Any):
    """Explain the supported arguments instead of leaking implementation errors.

    Args:
        component: An invalid public API argument.
    """
    with RegistrationContext() as context:
        with pytest.raises(
            TypeError,
            match="library name as a str or a prototype Component instance",
        ):
            dynamic.bundle_library(component)
        assert context.bundled_libraries == _default_bundled_libraries()
        assert not context._explicit_bundled_libraries


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
