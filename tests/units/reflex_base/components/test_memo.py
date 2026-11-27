"""Tests for compiler-generated memo definitions."""

import dataclasses
import inspect
import re
from unittest.mock import patch

import pytest
from reflex_base import constants
from reflex_base.components import memo
from reflex_base.components.component import PROHIBITED_LIBRARY_IMPORTS, Component
from reflex_base.components.component import field as component_field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.registry import RegistrationContext
from reflex_base.utils import memo_paths
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_components_core.base.bare import Bare
from reflex_components_core.el.elements.forms import Form, Input
from reflex_components_core.el.elements.typography import Div

import reflex as rx
from reflex.compiler import utils


@pytest.mark.parametrize("snapshot", [False, True])
@pytest.mark.parametrize("has_children", [False, True])
def test_auto_memo_evaluates_body_once(snapshot: bool, has_children: bool):
    """Generated wrappers reuse their body and fixed parameter metadata."""
    component = Div.create("child") if has_children else Div.create()
    original_children = list(component.children)
    component._memoization_mode = MemoizationMode(recursive=not snapshot)
    with patch.object(
        memo, "_evaluate_memo_function", wraps=memo._evaluate_memo_function
    ) as evaluate:
        factory, definition = memo.create_passthrough_component_memo(component)
        wrapper = factory()
        assert evaluate.call_count == 1

    assert definition.params == memo._analyze_params(definition.fn, for_component=True)
    assert isinstance(wrapper, memo.MemoComponent)
    assert definition.component is not component
    assert component.children == original_children
    if has_children and not snapshot:
        assert definition.passthrough_hole_child is definition.component.children[0]
        assert isinstance(definition.passthrough_hole_child, Bare)
        assert isinstance(component.children[0], Bare)
        assert str(definition.passthrough_hole_child.contents) == "children"
        assert str(component.children[0].contents) != "children"
    else:
        assert definition.passthrough_hole_child is None
        assert definition.component.children == component.children
    assert isinstance(definition.fn(Var(_js_expr="children", _var_type=Component)), Div)


def test_auto_memo_snapshot_renders_lifted_rest_props():
    """The retained memo body must render props lifted out of its children."""
    component = Div.create(Bare.create(memo._rest_placeholder("rest")))
    component._memoization_mode = MemoizationMode(recursive=False)
    _, definition = memo.create_passthrough_component_memo(component)
    rendered = definition.component.render()
    assert rendered["children"] == []
    assert "...rest" in rendered["props"]
    assert component.children


@pytest.mark.parametrize("forward_root_props", [False, True])
def test_memo_emission_reuses_unchanged_body_analysis(forward_root_props: bool):
    """Hashing and emission share a render when root styling changes nothing."""
    with RegistrationContext.ensure_context().fork() as context:
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        definition = dataclasses.replace(
            definition, forward_root_props=forward_root_props
        )
        analysis = context._memo_body_analyses[
            definition.component.__dict__["_memo_analysis_key"]
        ]
        with patch.object(
            Div, "render", autospec=True, side_effect=Div.render
        ) as render:
            compiled, _ = utils.compile_experimental_component_memo(definition)
            render.assert_not_called()
        if forward_root_props:
            assert compiled["render"]["children"] is analysis.rendered["children"]
        else:
            assert compiled["render"] is analysis.rendered


def test_memo_analysis_is_reset_with_registration_context():
    """A definition carried into another context is analyzed there afresh."""
    with RegistrationContext.ensure_context().fork() as context:
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        assert context._memo_body_analyses
        with context.fork() as fork:
            assert not fork._memo_body_analyses
            with patch.object(
                Div, "render", autospec=True, side_effect=Div.render
            ) as render:
                utils.compile_experimental_component_memo(definition)
                render.assert_called_once()


def test_identical_memo_bodies_share_one_analysis():
    """Repeated bodies retain one analysis that can serve each equivalent copy."""
    with RegistrationContext.ensure_context().fork() as context:
        first = Div.create("child")
        second = Div.create("child")
        digest = memo.component_hash(first, recursive=False)
        analysis = context._memo_body_analyses[digest]
        assert memo.component_hash(second, recursive=False) == digest
        assert context._memo_body_analyses[digest] is analysis
        assert analysis.can_reuse(second)


def test_memo_analysis_is_invalidated_with_component_caches():
    """Explicitly invalidating a mutated body also invalidates its analysis."""
    with RegistrationContext.ensure_context().fork():
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        definition.component.style["color"] = "blue"
        definition.component._clear_compile_caches()
        assert "_memo_analysis_key" not in definition.component.__dict__
        compiled, _ = utils.compile_experimental_component_memo(definition)
        assert any("blue" in prop for prop in compiled["render"]["props"])


def test_memo_analysis_is_not_reused_when_app_style_changes(monkeypatch):
    """Applying a new app style must render and collect its new dependencies."""
    with RegistrationContext.ensure_context().fork():
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        monkeypatch.setattr(utils, "_app_style", lambda: {Div: {"color": "red"}})
        compiled, _ = utils.compile_experimental_component_memo(definition)
        assert any("red" in prop for prop in compiled["render"]["props"])


def test_memo_analysis_checks_style_dependencies_even_when_css_matches():
    """Equivalent CSS can still acquire additional imports during root styling."""

    class StyledDiv(Div):
        """A component whose default style contributes an extra import."""

        def add_style(self):
            """Return a style with additional metadata.

            Returns:
                The style and its import-bearing Var.
            """
            return {
                "color": Var(
                    "sharedColor",
                    str,
                    VarData(imports={"extra": [ImportVar("useExtra")]}),
                )
            }

    with RegistrationContext.ensure_context().fork():
        component = StyledDiv.create("child", color=Var("sharedColor", str))
        _, definition = memo.create_passthrough_component_memo(component)
        _, imports = utils.compile_experimental_component_memo(definition)
        assert "extra" in imports


def test_memo_analysis_does_not_bypass_custom_copy():
    """A custom copy can change fields besides the root's style."""

    class CopyDiv(Div):
        """A component whose copies carry an increasing marker."""

        def __copy__(self):
            """Copy the component and advance its marker.

            Returns:
                A component with the next marker value.
            """
            clone = super().__copy__()
            assert isinstance(clone, CopyDiv)
            count = self.custom_attrs.get("data-copy", 0)
            assert isinstance(count, int)
            clone.custom_attrs = {"data-copy": count + 1}
            return clone

    with RegistrationContext.ensure_context().fork():
        _, definition = memo.create_passthrough_component_memo(CopyDiv.create("child"))
        compiled, _ = utils.compile_experimental_component_memo(definition)
        assert any('"data-copy":2' in prop for prop in compiled["render"]["props"])


def test_passthrough_memo_excludes_descendant_imports_and_keeps_prop_imports():
    """Passthrough memos keep root and prop imports while dropping descendants'."""

    class PropSlot(Component):
        tag = "PropSlot"
        library = "prop-slot-lib"

    class ParentWithSlot(Component):
        tag = "ParentWithSlot"
        library = "parent-lib"
        slot: Component | None = component_field(default=None)

    class DescendantLib(Component):
        tag = "DescendantLib"
        library = "descendant-lib"

    with RegistrationContext.ensure_context().fork():
        hole = Bare.create(Var(_js_expr="children", _var_type=Component))
        child_state = rx.client_state(0)
        child_memo_specifier = memo_paths.unmirrored_library_specifier("ChildMemo")
        child_wrapper = Div.create(
            child_state.value,
            custom_attrs={
                "data-memo": Var(
                    "ChildMemo",
                    _var_data=VarData(
                        imports={child_memo_specifier: [ImportVar(tag="ChildMemo")]}
                    ),
                )
            },
            on_mount=rx.console_log("descendant"),
        )
        descendant = DescendantLib.create(
            child_wrapper,
            Var(
                "descVar",
                _var_data=VarData(imports={"desc-var-lib": [ImportVar(tag="descVar")]}),
            ),
        )
        parent = ParentWithSlot.create(descendant, slot=PropSlot.create())
        definition = memo.MemoComponentDefinition(
            fn=lambda children: parent,
            python_name="parent_with_slot",
            params=(
                memo.MemoParam(
                    name="children",
                    kind=memo.MemoParamKind.CHILDREN,
                    annotation=Component,
                    parameter_kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    js_prop_name="children",
                    placeholder_name="children",
                ),
            ),
            export_name="ParentMemo",
            _component=memo._LazyBody.ready(parent),
            passthrough_hole_child=hole,
            forward_root_props=True,
            is_instance_boundary=True,
        )
        compiled, imports = utils.compile_experimental_component_memo(definition)

    assert imports == {
        "parent-lib": [ImportVar(tag="ParentWithSlot")],
        "prop-slot-lib": [ImportVar(tag="PropSlot")],
        "@emotion/react": [ImportVar(tag="jsx")],
        "react": [ImportVar(tag="memo")],
        f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="mergeSlotProps")],
    }
    assert compiled["wrapper"] == "memo"
    assert compiled["render"] == {
        "name": "ParentWithSlot",
        "props": ["...mergeSlotProps(rest, ({ slot:(jsx(PropSlot, ({}))) }))"],
        "children": [{"contents": "children"}],
    }


def test_passthrough_memo_root_client_state_retains_instance_boundary_scope():
    """Root client state on a passthrough boundary still emits a state scope."""

    class DescendantLib(Component):
        tag = "DescendantLib"
        library = "descendant-lib"

    with RegistrationContext.ensure_context().fork():
        hole = Bare.create(Var(_js_expr="children", _var_type=Component))
        root_state = rx.client_state(0)
        parent = Div.create(
            DescendantLib.create("child"),
            custom_attrs={"data-cs": root_state.value},
        )
        definition = memo.MemoComponentDefinition(
            fn=lambda children: parent,
            python_name="root_cs_div",
            params=(
                memo.MemoParam(
                    name="children",
                    kind=memo.MemoParamKind.CHILDREN,
                    annotation=Component,
                    parameter_kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    js_prop_name="children",
                    placeholder_name="children",
                ),
            ),
            export_name="RootCsDiv",
            _component=memo._LazyBody.ready(parent),
            passthrough_hole_child=hole,
            is_instance_boundary=True,
        )
        compiled, imports = utils.compile_experimental_component_memo(definition)

    assert (
        re.sub(r"cs\$\d+", "cs$0", compiled["wrapper"])
        == '((Component) => withClientStateScope(memo(Component), ["cs$0"]))'
    )
    assert imports == {
        f"$/{constants.Dirs.CLIENT_STATE_PATH}": [
            ImportVar(tag="useClientState"),
            ImportVar(tag="withClientStateScope"),
        ],
        "@emotion/react": [ImportVar(tag="jsx")],
        "react": [ImportVar(tag="memo")],
    }


def test_passthrough_memo_retains_root_add_hooks_and_form_refs():
    """Root ``add_hooks`` and form ref imports survive omitting descendants."""

    class DescendantLib(Component):
        tag = "DescendantLib"
        library = "descendant-lib"

    class RootWithChildHook(Div):
        def add_imports(self):
            return (
                {"root-added-lib": [ImportVar(tag="rootAddedHelper")]}
                if self.children
                else {}
            )

        def add_hooks(self):
            return [
                "useRootAdded(rootAddedHelper)" if self.children else "",
                Var(
                    "rootHookCall",
                    _var_data=VarData(
                        imports={"root-hook-var-lib": [ImportVar(tag="useRootHook")]}
                    ),
                ),
            ]

    with RegistrationContext.ensure_context().fork():
        hole = Bare.create(Var(_js_expr="children", _var_type=Component))
        form_comp = Form.create(
            Input.create(id="field_a"),
            DescendantLib.create("child"),
            id="f",
        )
        form_def = memo.MemoComponentDefinition(
            fn=lambda children: form_comp,
            python_name="form_wrapper",
            params=(
                memo.MemoParam(
                    name="children",
                    kind=memo.MemoParamKind.CHILDREN,
                    annotation=Component,
                    parameter_kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    js_prop_name="children",
                    placeholder_name="children",
                ),
            ),
            export_name="FormWrapper",
            _component=memo._LazyBody.ready(form_comp),
            passthrough_hole_child=hole,
        )
        _, form_imports = utils.compile_experimental_component_memo(form_def)

        root_hook_comp = RootWithChildHook.create(DescendantLib.create("child"))
        root_hook_def = memo.MemoComponentDefinition(
            fn=lambda children: root_hook_comp,
            python_name="root_hook_comp",
            params=(
                memo.MemoParam(
                    name="children",
                    kind=memo.MemoParamKind.CHILDREN,
                    annotation=Component,
                    parameter_kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    js_prop_name="children",
                    placeholder_name="children",
                ),
            ),
            export_name="RootHookMemo",
            _component=memo._LazyBody.ready(root_hook_comp),
            passthrough_hole_child=hole,
        )
        root_hook_compiled, root_hook_imports = (
            utils.compile_experimental_component_memo(root_hook_def)
        )

    assert form_imports == {
        f"$/{constants.Dirs.STATE_PATH}": [
            ImportVar(tag="useRegisteredRef"),
            ImportVar(tag="ReflexEvent"),
            ImportVar(tag="applyEventActions"),
            ImportVar(tag="refs"),
            ImportVar(tag="getFormData"),
            ImportVar(tag="getRefValue"),
            ImportVar(tag="getRefValues"),
        ],
        f"$/{constants.Dirs.CONTEXTS_PATH}": [ImportVar(tag="addEvents")],
        "react": [ImportVar(tag="useCallback"), ImportVar(tag="memo")],
        "@emotion/react": [ImportVar(tag="jsx")],
    }
    assert root_hook_compiled["hooks"] == {
        "useRootAdded(rootAddedHelper)": None,
        "rootHookCall": VarData(
            imports={"root-hook-var-lib": [ImportVar(tag="useRootHook")]}
        ),
    }
    assert root_hook_imports == {
        "root-hook-var-lib": [ImportVar(tag="useRootHook")],
        "root-added-lib": [ImportVar(tag="rootAddedHelper")],
        "@emotion/react": [ImportVar(tag="jsx")],
        "react": [ImportVar(tag="memo")],
    }


def test_passthrough_memo_analysis_reuse_keeps_cached_imports_isolated():
    """Compiling a passthrough memo must not mutate cached analysis imports."""
    with RegistrationContext.ensure_context().fork() as context:
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        analysis = context._memo_body_analyses[
            definition.component.__dict__["_memo_analysis_key"]
        ]
        assert analysis.imports == {}
        _, compiled_imports = utils.compile_experimental_component_memo(definition)
        assert analysis.imports == {}
        assert compiled_imports == {
            "@emotion/react": [ImportVar(tag="jsx")],
            "react": [ImportVar(tag="memo")],
            f"$/{constants.Dirs.STATE_PATH}": [ImportVar(tag="mergeSlotProps")],
        }


@pytest.mark.parametrize(
    "bad_package",
    ["react-router-dom", "react-router-dom/server", "react-router-dom@7.18.2"],
)
def test_passthrough_memo_rejects_prohibited_pre_swap_root_imports(bad_package: str):
    """Pre-swap child-conditional ``add_imports`` and hook imports are validated."""

    class BadConditionalAddImports(Div):
        def add_imports(self):
            return {bad_package: [ImportVar(tag="Link")]} if self.children else {}

    class BadConditionalHookImports(Div):
        def add_hooks(self):
            return (
                [
                    Var(
                        "badHook",
                        _var_data=VarData(
                            imports={bad_package: [ImportVar(tag="useBad")]}
                        ),
                    )
                ]
                if self.children
                else []
            )

    with RegistrationContext.ensure_context().fork():
        hole = Bare.create(Var(_js_expr="children", _var_type=Component))
        for bad_cls in (BadConditionalAddImports, BadConditionalHookImports):
            comp = bad_cls.create(Div.create("child"))
            definition = memo.MemoComponentDefinition(
                fn=lambda children, comp=comp: comp,
                python_name=bad_cls.__name__,
                params=(
                    memo.MemoParam(
                        name="children",
                        kind=memo.MemoParamKind.CHILDREN,
                        annotation=Component,
                        parameter_kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        js_prop_name="children",
                        placeholder_name="children",
                    ),
                ),
                export_name=bad_cls.__name__,
                _component=memo._LazyBody.ready(comp),
                passthrough_hole_child=hole,
            )
            with pytest.raises(ValueError) as exc_info:
                utils.compile_experimental_component_memo(definition)
            assert str(exc_info.value) == (
                f"The component `{bad_cls.__name__}` references `{bad_package}`, "
                f"but {PROHIBITED_LIBRARY_IMPORTS['react-router-dom']}"
            )
