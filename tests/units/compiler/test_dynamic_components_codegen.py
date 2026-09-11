"""Code generation tests for dynamic components."""

import dataclasses
from pathlib import Path

import pytest
from reflex_base.components.dynamic import (
    _reset_bundled_libraries_for_compile,
    bundle_library,
)
from reflex_base.registry import RegistrationContext
from reflex_base.utils import serializers
from reflex_base.utils.imports import ImportVar, ParsedImportDict
from reflex_base.vars.base import Var

import reflex as rx
from reflex.compiler import compiler
from reflex.state import State

STATE_JS_TEMPLATE = (
    Path(__file__).parents[3]
    / "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"
)


def test_dynamic_component_codegen_rewrites_bundled_library_subpath() -> None:
    """Bundled Lucide subpaths resolve through their own window namespaces."""
    with RegistrationContext():
        bundle_library("lucide-react")
        code = serializers.serialize(rx.icon("apple"))
        dynamic_code = serializers.serialize(rx.icon(Var("icon_name").to(str)))
        _, app_root_code = compiler.compile_app_root(rx.el.div())

    assert isinstance(code, str)
    assert 'from "lucide-react/dist/esm/icons/apple.mjs"' not in code
    assert (
        "const LucideApple = "
        "window.__reflex['lucide-react/dist/esm/icons/apple.mjs'].default"
    ) in code
    assert isinstance(dynamic_code, str)
    assert 'from "lucide-react/dynamic.mjs"' not in dynamic_code
    assert (
        "const {DynamicIcon} = window.__reflex['lucide-react/dynamic.mjs']"
    ) in dynamic_code
    assert (
        "import * as lucide_react_dist_esm_icons_apple_mjs "
        'from "lucide-react/dist/esm/icons/apple.mjs";'
    ) in app_root_code


@pytest.mark.parametrize("reactive", [False, True])
def test_component_registration_bundles_subpaths_before_serialization(reactive: bool):
    """Prebundle a component that is absent from the initial state.

    Args:
        reactive: Whether the component uses a named dynamic-icon import.
    """
    icon = rx.icon(Var("icon_name").to(str)) if reactive else rx.icon("apple")
    subpath = (
        "lucide-react/dynamic.mjs"
        if reactive
        else "lucide-react/dist/esm/icons/apple.mjs"
    )
    with RegistrationContext() as context:
        bundle_library(icon)
        bundle_library(icon)
        with context.fork():
            _reset_bundled_libraries_for_compile()
            _, app_root_code = compiler.compile_app_root(rx.el.div())
            assert f'from "{subpath}";' in app_root_code
            assert 'from "lucide-react";' not in app_root_code
            assert RegistrationContext.get().bundled_libraries.count(subpath) == 1
            code = serializers.serialize(icon)
        assert isinstance(code, str)
        assert f"window.__reflex['{subpath}']" in code


@pytest.mark.parametrize("reactive", [False, True])
def test_explicit_subpath_registration_does_not_require_package_root(reactive: bool):
    """Honor an exact subpath registration without sending it to a CDN.

    Args:
        reactive: Whether the component uses a named dynamic-icon import.
    """
    icon = rx.icon(Var("icon_name").to(str)) if reactive else rx.icon("apple")
    subpath = (
        "lucide-react/dynamic.mjs"
        if reactive
        else "lucide-react/dist/esm/icons/apple.mjs"
    )
    with RegistrationContext() as context:
        bundle_library(subpath)
        assert "lucide-react" not in context.bundled_libraries
        _, app_root_code = compiler.compile_app_root(rx.el.div())
        code = serializers.serialize(icon)
        assert "lucide-react" not in context.bundled_libraries
    assert f'from "{subpath}";' in app_root_code
    assert isinstance(code, str)
    assert f"window.__reflex['{subpath}']" in code
    assert "cdn.jsdelivr.net/npm/lucide-react" not in code


@pytest.mark.parametrize("library", ["test-library@1.0.0", "@test/library@1.0.0"])
@pytest.mark.parametrize("is_default", [False, True])
def test_component_registration_uses_import_var_subpath(library: str, is_default: bool):
    """Bundle a specialized component's module without its unused package root.

    Args:
        library: The versioned package containing the component.
        is_default: Whether the specialized module exports the component by default.
    """

    class SubpathComponent(rx.Component):
        """A component that declares its deep import through import_var."""

        tag = "Widget"
        alias = "DeepWidget"

        @property
        def import_var(self) -> ImportVar:
            """Import the component directly from its specialized module.

            Returns:
                The component's default or named subpath import.
            """
            return ImportVar(
                self.tag,
                alias=self.alias,
                is_default=is_default,
                package_path="/deep.mjs",
            )

    component = SubpathComponent.create(library=library)
    root = library.removesuffix("@1.0.0")
    subpath = f"{root}/deep.mjs"
    with RegistrationContext() as context:
        bundle_library(component)
        with context.fork() as forked:
            _reset_bundled_libraries_for_compile()
            _, app_root_code = compiler.compile_app_root(rx.el.div())
            assert f'from "{root}";' not in app_root_code
            assert f'from "{subpath}";' in app_root_code
            assert root not in forked.bundled_libraries
            code = serializers.serialize(component)
            assert root not in forked.bundled_libraries
    assert isinstance(code, str)
    declaration = (
        f"const DeepWidget = window.__reflex['{subpath}'].default"
        if is_default
        else f"const {{Widget: DeepWidget}} = window.__reflex['{subpath}']"
    )
    assert declaration in code
    assert "cdn.jsdelivr.net/npm/" not in code


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        (
            [ImportVar("Widget", is_default=True, alias="DeepWidget")],
            ["const DeepWidget = {window}.default"],
        ),
        (
            [ImportVar("Widget", alias="DeepWidget")],
            ["const {Widget: DeepWidget} = {window}"],
        ),
        ([ImportVar("*", alias="DeepNamespace")], ["const DeepNamespace = {window}"]),
        (
            [
                ImportVar("Widget", is_default=True),
                ImportVar("value", alias="deepValue"),
            ],
            ["const Widget = {window}.default", "const {value: deepValue} = {window}"],
        ),
    ],
)
@pytest.mark.parametrize("bundle_root", [False, True])
def test_dynamic_component_bundled_subpath_import_forms(
    fields: list[ImportVar], expected: list[str], bundle_root: bool
):
    """Preserve default, named, namespace and mixed bindings from exact subpaths.

    Args:
        fields: Import bindings requested from the subpath.
        expected: Declarations expected in the dynamic module.
        bundle_root: Whether the root package or only the subpath is registered.
    """
    test_library = "test-library@1.0.0"

    class SubpathComponent(rx.Component):
        """A component with an additional bundled subpath dependency."""

        library = test_library
        tag = "RootComponent"

        def add_imports(self) -> ParsedImportDict:
            """Import bindings from a module below the package root.

            Returns:
                The requested versioned subpath imports.
            """
            return {
                test_library: [
                    dataclasses.replace(field, package_path="/deep.mjs")
                    for field in fields
                ]
            }

    with RegistrationContext() as context:
        bundle_library("test-library" if bundle_root else "test-library/deep.mjs")
        code = serializers.serialize(SubpathComponent.create())
        assert isinstance(code, str)
        assert 'from "test-library/deep.mjs"' not in code
        for declaration in expected:
            assert (
                declaration.replace(
                    "{window}", "window.__reflex['test-library/deep.mjs']"
                )
                in code
            )
        assert context.bundled_libraries.count("test-library/deep.mjs") == 1
        if not bundle_root:
            assert 'from "https://cdn.jsdelivr.net/npm/test-library@1.0.0/+esm"' in code


def test_dynamic_component_codegen_wires_event_handlers() -> None:
    """Dynamic component codegen should preserve backend event handlers."""
    state = State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    component = rx.el.div(
        rx.el.button("hydrate", on_click=State.set_is_hydrated(True)),
        rx.el.span(state.is_hydrated),
        rx.el.button("unhydrate", on_click=State.set_is_hydrated(False)),
    )
    code = serializers.serialize(component)

    assert isinstance(code, str)
    assert code.startswith("//__reflex_evaluate")
    assert "const {Fragment,useEffect}" in code
    # ``addEvents`` is now a module-level callable in ``$/utils/context``;
    # no more ``useContext(EventLoopContext)`` hoist needed for dispatch.
    assert "const {addEvents} = window['__reflex'][\"$/utils/context\"]" in code
    assert (
        "const {ReflexEvent,applyEventActions,pyOr} = window['__reflex'][\"$/utils/state\"]"
        in code
    )
    assert "useContext(EventLoopContext)" not in code
    assert code.count("onClick:") == 2
    assert code.count("addEvents(") == 2
    assert code.count("ReflexEvent(") == 2
    assert (
        'ReflexEvent("reflex___state____state.set_is_hydrated", '
        '({ ["value"] : true }), ({  }))'
    ) in code
    assert (
        'ReflexEvent("reflex___state____state.set_is_hydrated", '
        '({ ["value"] : false }), ({  }))'
    ) in code


def test_dynamic_component_codegen_wires_state_var_counter_events() -> None:
    """Dynamic component codegen should preserve stateful counter event handlers."""

    class DynamicCounterCodegenState(rx.State):
        count: int = 0

        @rx.event
        def set_count(self, count: int):
            """Set the counter value.

            Args:
                count: The new counter value.
            """
            self.count = count

        @rx.var
        def counter_ui(self) -> rx.Component:
            """Get a dynamic counter component.

            Returns:
                The dynamic counter component.
            """
            return rx.hstack(
                rx.button(
                    "-",
                    on_click=DynamicCounterCodegenState.set_count(self.count - 1),
                ),
                rx.text(self.count, size="9"),
                rx.button(
                    "+",
                    on_click=DynamicCounterCodegenState.set_count(self.count + 1),
                ),
                spacing="5",
                justify="center",
            )

    state = DynamicCounterCodegenState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
    code = serializers.serialize(state.counter_ui)

    assert isinstance(code, str)
    assert code.startswith("//__reflex_evaluate")
    assert "RadixThemesFlex" in code
    assert "RadixThemesButton" in code
    assert "RadixThemesText" in code
    assert 'justify:"center"' in code
    assert 'gap:"5"' in code
    assert "const {Fragment,useEffect}" in code
    assert "const {addEvents} = window['__reflex'][\"$/utils/context\"]" in code
    assert (
        "const {ReflexEvent,applyEventActions,pyOr} = window['__reflex'][\"$/utils/state\"]"
        in code
    )
    assert "useContext(EventLoopContext)" not in code
    assert code.count("onClick:") == 2
    assert code.count("addEvents(") == 2
    assert code.count("ReflexEvent(") == 2
    assert code.count(".set_count") == 2
    assert '({ ["count"] : -1 }), ({  })' in code
    assert '({ ["count"] : 1 }), ({  })' in code
    assert 'jsx(RadixThemesText, ({as:"p",size:"9"}), 0)' in code
