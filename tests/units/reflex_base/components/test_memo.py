"""Tests for compiler-generated memo definitions."""

from unittest.mock import patch

import pytest
from reflex_base.components import memo
from reflex_base.components.component import Component
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.registry import RegistrationContext
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_components_core.base.bare import Bare
from reflex_components_core.el.elements.typography import Div

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
        assert definition.component is definition.component
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


def test_memo_emission_reuses_unchanged_body_analysis():
    """Hashing and emission share a render when root styling changes nothing."""
    with RegistrationContext.ensure_context().fork() as context:
        _, definition = memo.create_passthrough_component_memo(Div.create("child"))
        analysis = context._memo_body_analyses[
            definition.component.__dict__["_memo_analysis_key"]
        ]
        with patch.object(
            Div, "render", autospec=True, side_effect=Div.render
        ) as render:
            compiled, _ = utils.compile_experimental_component_memo(definition)
            render.assert_not_called()
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
        assert '"data-copy":2' in compiled["render"]["props"]
