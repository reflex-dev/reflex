from __future__ import annotations

import asyncio

import pytest
from reflex_base.components.component import Component
from reflex_base.components.component import field as component_field

from reflex.compiler.utils import _collect_subtree_artifacts, compile_state
from reflex.constants.state import FIELD_MARKER
from reflex.state import State
from reflex.vars.base import computed_var


class CompileStateState(State):
    """State fixture exercising async computed vars during compile_state."""

    a: int = 1
    b: int = 2

    @computed_var
    async def async_value(self) -> str:
        """Return a resolved value after yielding to the event loop.

        Returns:
            The resolved string value.
        """
        await asyncio.sleep(0)
        return "resolved"


def _get_state_values(compiled: dict, state: type[State]) -> dict:
    return compiled[state.get_full_name()]


def test_compile_state_resolves_async_computed_vars_without_event_loop():
    compiled = compile_state(CompileStateState)
    values = _get_state_values(compiled, CompileStateState)
    assert values[f"a{FIELD_MARKER}"] == 1
    assert values[f"b{FIELD_MARKER}"] == 2
    assert values[f"async_value{FIELD_MARKER}"] == "resolved"


@pytest.mark.asyncio
async def test_compile_state_resolves_async_computed_vars_with_running_event_loop():
    assert asyncio.get_running_loop() is not None
    await asyncio.sleep(0)
    compiled = compile_state(CompileStateState)
    values = _get_state_values(compiled, CompileStateState)
    assert values[f"a{FIELD_MARKER}"] == 1
    assert values[f"b{FIELD_MARKER}"] == 2
    assert values[f"async_value{FIELD_MARKER}"] == "resolved"


class ArtifactChild(Component):
    """Leaf component contributing hooks, custom code, and a dynamic import."""

    library = "artifact-child-lib"
    tag = "ArtifactChild"

    def add_hooks(self) -> list[str]:
        """Contribute a hook line.

        Returns:
            The hook lines for this component.
        """
        return ["const artifactChildHook = 1;"]

    def _get_custom_code(self) -> str | None:
        return "const artifactChildCustom = 1;"

    def _get_dynamic_imports(self) -> str | None:
        return "artifact-child-dynamic"


class ArtifactProp(Component):
    """Component used inside a prop slot, with its own custom code."""

    library = "artifact-prop-lib"
    tag = "ArtifactProp"

    def add_hooks(self) -> list[str]:
        """Contribute a hook line (must not leak out of the prop tree).

        Returns:
            The hook lines for this component.
        """
        return ["const artifactPropHook = 1;"]

    def _get_custom_code(self) -> str | None:
        return "const artifactPropCustom = 1;"


class ArtifactRoot(Component):
    """Root component with a component-typed prop slot and class custom code."""

    library = "artifact-root-lib"
    tag = "ArtifactRoot"

    slot: Component | None = component_field(default=None)

    def add_hooks(self) -> list[str]:
        """Contribute a hook line.

        Returns:
            The hook lines for this component.
        """
        return ["const artifactRootHook = 1;"]

    def add_custom_code(self) -> list[str]:
        """Contribute class-level custom code.

        Returns:
            The custom code lines for this component.
        """
        return ["const artifactRootAddCustom = 1;"]


def test_collect_subtree_artifacts_matches_legacy_walks():
    """The fused artifact walk matches the four legacy recursions exactly.

    Order-sensitive: hooks and custom code dict ordering determines the
    emitted JS, so the fused walk must reproduce each legacy recursion's
    insertion order (including custom code from prop subtrees landing before
    the component's own ``add_custom_code`` contributions, and hooks never
    being collected from prop subtrees).
    """
    root = ArtifactRoot.create(
        ArtifactChild.create(),
        ArtifactChild.create(id="artifact-ref"),
        slot=ArtifactProp.create(ArtifactChild.create()),
    )

    fused_hooks, fused_custom, fused_dynamic, fused_imports = (
        _collect_subtree_artifacts(root)
    )

    legacy_hooks = root._get_all_hooks()
    assert fused_hooks == legacy_hooks
    assert list(fused_hooks) == list(legacy_hooks)
    assert "const artifactPropHook = 1;" not in fused_hooks

    legacy_custom = root._get_all_custom_code()
    assert fused_custom == legacy_custom
    assert list(fused_custom) == list(legacy_custom)

    assert fused_dynamic == root._get_all_dynamic_imports()

    legacy_imports = root._get_all_imports()
    assert fused_imports == legacy_imports
    assert list(fused_imports) == list(legacy_imports)
