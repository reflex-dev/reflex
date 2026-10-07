from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

import pytest
from reflex_base import constants
from reflex_base.components.memo import create_passthrough_component_memo
from reflex_base.registry import RegistrationContext
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.base.script import Script
from reflex_components_core.el.elements.metadata import Link
from reflex_components_core.el.elements.typography import Div

import reflex as rx
from reflex.compiler import utils
from reflex.compiler.utils import compile_state, create_document_root
from reflex.compiler.utils import write_file as compiler_write_file
from reflex.constants.state import FIELD_MARKER
from reflex.state import State, state_snapshot_hashes
from reflex.utils.path_ops import write_file
from reflex.vars.base import computed_var


def test_memo_root_prop_forwarding_preserves_cached_analysis() -> None:
    """Repeated emission of shared memo bodies must not accumulate prop merges."""
    with RegistrationContext.ensure_context().fork() as context:
        _, first = create_passthrough_component_memo(Div.create("first", id="root"))
        _, second = create_passthrough_component_memo(Div.create("second", id="root"))
        assert first.export_name == second.export_name
        analysis = context._memo_body_analyses[
            first.component.__dict__["_memo_analysis_key"]
        ]
        original_render = deepcopy(analysis.rendered)

        for definition in (first, first, second):
            compiled, _ = utils.compile_experimental_component_memo(definition)
            props = ", ".join(compiled["render"]["props"])
            assert props.count("mergeSlotProps(") == 1
            assert "ref:ref_root" in props
            assert analysis.rendered == original_render


def test_write_file_reexport() -> None:
    """Existing compiler callers retain the shared file-writing helper."""
    assert compiler_write_file is write_file


def test_bundled_libraries_artifact_round_trip(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backend-only workers can restore the registry from the frontend build."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    with RegistrationContext() as context:
        context.bundled_libraries.append("@radix-ui/themes")
        output_path, output = utils._compile_bundled_libraries()
        artifact_path = tmp_path / output_path
        artifact_path.parent.mkdir()
        artifact_path.write_text(output, encoding="utf-8")
        context.bundled_libraries[:] = ["react"]

        utils._restore_bundled_libraries()

        assert context.bundled_libraries == [
            "react",
            "@emotion/react",
            "$/utils/context",
            "$/utils/state",
            "@radix-ui/themes",
        ]


def test_restore_bundled_libraries_preserves_page_registrations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restoring frontend metadata retains libraries discovered by page evaluation."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_text('["@radix-ui/themes"]', encoding="utf-8")
    with RegistrationContext() as context:
        context.bundled_libraries.append("page-library")

        utils._restore_bundled_libraries()

        assert "@radix-ui/themes" in context.bundled_libraries
        assert "page-library" in context.bundled_libraries


def test_restore_bundled_libraries_ignores_invalid_utf8(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed registry artifacts do not interrupt backend-only startup."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_bytes(b"\xff")

    utils._restore_bundled_libraries()


@pytest.mark.parametrize(
    "contents",
    ["{", '"@radix-ui/themes"', '["@radix-ui/themes", 1]'],
)
def test_restore_bundled_libraries_ignores_invalid_json(
    tmp_path, monkeypatch: pytest.MonkeyPatch, contents: str
) -> None:
    """Malformed registry data does not change backend registrations."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)
    artifact_path = tmp_path / utils.constants.Dirs.BUNDLED_LIBRARIES
    artifact_path.parent.mkdir()
    artifact_path.write_text(contents, encoding="utf-8")
    with RegistrationContext() as context:
        original = list(context.bundled_libraries)

        utils._restore_bundled_libraries()

        assert context.bundled_libraries == original


def test_restore_bundled_libraries_ignores_missing_artifact(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing frontend artifact does not interrupt backend-only startup."""
    monkeypatch.setattr(utils, "get_web_dir", lambda: tmp_path)

    utils._restore_bundled_libraries()


def _global_stylesheet_links() -> list[list[str]]:
    """Render the framework link tags of a fresh document head.

    Returns:
        The rendered props of every ``Link`` in the head.
    """
    head = create_document_root().children[0]
    return [
        child.render()["props"] for child in head.children if isinstance(child, Link)
    ]


def test_document_preloads_the_global_stylesheet_in_prod(
    monkeypatch: pytest.MonkeyPatch,
):
    """Production builds hint the render-blocking CSS ahead of the stylesheet link.

    Args:
        monkeypatch: Selects prod mode and restores the previous mode afterwards.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.PROD.value)
    links = _global_stylesheet_links()
    preload = next(props for props in links if 'rel:"preload"' in props)
    stylesheet = next(props for props in links if 'rel:"stylesheet"' in props)
    assert next(prop for prop in preload if prop.startswith("href:")) == next(
        prop for prop in stylesheet if prop.startswith("href:")
    )
    assert 'as:"style"' in preload


def test_document_does_not_preload_the_global_stylesheet_in_dev(
    monkeypatch: pytest.MonkeyPatch,
):
    """Dev builds link the stylesheet once so Vite's css-update swaps that link.

    Args:
        monkeypatch: Selects dev mode and restores the previous mode afterwards.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.DEV.value)
    links = _global_stylesheet_links()
    assert not any('rel:"preload"' in props for props in links)
    assert sum('rel:"stylesheet"' in props for props in links) == 1


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


def test_compile_state_hashes_dict_with_mixed_key_types(
    forked_registration_context: RegistrationContext,
):
    """A dict default mixing int and str keys compiles and hashes without comparing keys.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """

    class MixedKeyState(State):
        mapping: dict[str | int, str] = {1: "one", "two": "two"}

    compiled = compile_state(MixedKeyState)
    assert _get_state_values(compiled, MixedKeyState) == {
        f"mapping{FIELD_MARKER}": {1: "one", "two": "two"}
    }
    assert len(state_snapshot_hashes(compiled)) == len(compiled) + 1


def test_compile_client_storage_honors_default_factories(
    forked_registration_context: RegistrationContext,
):
    """Factory-backed browser storage fields compile with the options they produce.

    Args:
        forked_registration_context: Keeps the test's state out of other tests.
    """

    class StorageState(State):
        cookie: rx.Field[rx.Cookie] = rx.field(
            default_factory=lambda: rx.Cookie("new", name="cookie-key", max_age=60)
        )
        local: rx.Field[rx.LocalStorage] = rx.field(
            default_factory=lambda: rx.LocalStorage("new", name="local-key", sync=True)
        )
        session: rx.Field[rx.SessionStorage] = rx.field(
            default_factory=rx.SessionStorage
        )

    StorageState.session = lambda: rx.SessionStorage("new", name="session-key")  # pyright: ignore[reportAttributeAccessIssue]
    compiled = utils.compile_client_storage(StorageState)
    name = StorageState.get_full_name()
    cookie = compiled[constants.COOKIES][f"{name}.cookie{FIELD_MARKER}"]
    assert (cookie["name"], cookie["maxAge"]) == ("cookie-key", 60)
    assert compiled[constants.LOCAL_STORAGE][f"{name}.local{FIELD_MARKER}"] == {
        "name": "local-key",
        "sync": True,
    }
    assert compiled[constants.SESSION_STORAGE][f"{name}.session{FIELD_MARKER}"] == {
        "name": "session-key"
    }


@pytest.mark.parametrize(
    ("storage_type", "settings", "expected_options"),
    [
        pytest.param(
            rx.Cookie,
            {
                "name": "custom-key",
                "path": "/app",
                "max_age": 60,
                "secure": True,
                "same_site": "strict",
            },
            {
                "name": "custom-key",
                "path": "/app",
                "maxAge": 60,
                "secure": True,
                "sameSite": "strict",
            },
            id="cookie",
        ),
        pytest.param(
            rx.LocalStorage,
            {"name": "custom-key", "sync": True},
            {"name": "custom-key", "sync": True},
            id="local_storage",
        ),
        pytest.param(
            rx.SessionStorage,
            {"name": "custom-key"},
            {"name": "custom-key"},
            id="session_storage",
        ),
    ],
)
def test_storage_factory_assignment_keeps_classification(
    storage_type: type,
    settings: dict[str, Any],
    expected_options: dict[str, Any],
    forked_registration_context: RegistrationContext,
):
    """A factory assigned to a str-annotated storage var is called once and stays storage.

    Args:
        storage_type: The browser storage type the declaration uses.
        settings: The storage options the factory configures.
        expected_options: The compiled options those settings produce.
        forked_registration_context: Keeps the test's state out of other tests.
    """
    calls = []

    def factory() -> str:
        """Produce the configured storage value, recording each call.

        Returns:
            The storage value.
        """
        calls.append(True)
        return storage_type("new", **settings)

    class StorageState(State):
        value: str = storage_type("old", name="custom-key")

    declared = StorageState.get_fields()["value"]
    StorageState.value = factory  # pyright: ignore[reportAttributeAccessIssue]
    assert calls == [True]
    assert declared.default_value() == "new"
    field_type, options = utils._compile_client_storage_field(declared)
    assert field_type is storage_type
    assert options is not None
    assert expected_options.items() <= options.items()
    state = StorageState(value="changed")
    state._reset_client_storage()
    assert state.value == "new"
    state._reset_client_storage()
    assert calls == [True]


@pytest.mark.parametrize("factory", [False, True])
@pytest.mark.parametrize("annotated_storage", [False, True])
@pytest.mark.parametrize(
    ("storage_type", "settings", "storage_key"),
    [
        pytest.param(
            rx.Cookie,
            {
                "name": "custom-key",
                "path": "/app",
                "max_age": 60,
                "secure": True,
                "same_site": "strict",
            },
            constants.COOKIES,
            id="cookie",
        ),
        pytest.param(
            rx.LocalStorage,
            {"name": "custom-key", "sync": True},
            constants.LOCAL_STORAGE,
            id="local_storage",
        ),
        pytest.param(
            rx.SessionStorage,
            {"name": "custom-key"},
            constants.SESSION_STORAGE,
            id="session_storage",
        ),
    ],
)
def test_plain_default_assignment_keeps_browser_storage(
    storage_type: type,
    settings: dict[str, Any],
    storage_key: str,
    annotated_storage: bool,
    factory: bool,
    forked_registration_context: RegistrationContext,
):
    """A plain default assigned to a browser storage var keeps its storage and options.

    Args:
        storage_type: The browser storage type the declaration uses.
        settings: The storage options of the declaration.
        storage_key: The compiled storage section listing the var.
        annotated_storage: Whether the var is annotated with the storage type, or str.
        factory: Whether to assign a factory producing the plain value.
        forked_registration_context: Keeps the test's state out of other tests.
    """
    declared_default = storage_type("old", **settings)
    storage_state: Any = type(
        "StorageState",
        (State,),
        {
            "__annotations__": {"value": storage_type if annotated_storage else str},
            "value": declared_default,
            "__module__": __name__,
        },
    )
    declared = storage_state.get_fields()["value"]
    storage_state.value = (lambda: "new") if factory else "new"

    assert type(declared.default) is storage_type
    assert declared.default == "new"
    assert vars(declared.default) == vars(declared_default)
    assert storage_state._is_client_storage("value")
    compiled = utils.compile_client_storage(storage_state)
    key = f"{storage_state.get_full_name()}.value{FIELD_MARKER}"
    assert compiled[storage_key][key] == declared_default.options()
    state = storage_state(value="changed")
    state._reset_client_storage()
    assert state.value == "new"

    with pytest.raises(TypeError, match="Invalid default"):
        storage_state.value = 1
    replacement = storage_type("other", name="other-key")
    storage_state.value = replacement
    assert declared.default is replacement


def test_document_root_allows_static_id_on_head_script():
    """A head script's ID should remain an HTML attribute without a hook."""
    head_script = Script.create(src="/probe.js", id="head-probe")
    document_root = create_document_root(head_components=[head_script])

    rendered = str(document_root.render())
    assert not document_root._get_all_hooks()
    assert 'id:"head-probe"' in rendered
    assert "ref_head_probe" not in rendered
    assert head_script._get_all_hooks()
    assert "ref_head_probe" in str(head_script.render())


def test_document_root_literalizes_nested_ids_without_mutating_original():
    """Nested head IDs are literalized on a copy of the user component."""
    nested_script = Script.create(src="/probe.js", id="nested-probe")
    head_component = Fragment.create(nested_script)
    document_root = create_document_root(head_components=[head_component])

    rendered = str(document_root.render())
    assert not document_root._get_all_hooks()
    assert 'id:"nested-probe"' in rendered
    assert "ref_nested_probe" not in rendered
    assert head_component._get_all_hooks()
    assert nested_script._get_all_hooks()


def test_document_root_controls_preserve_no_id_and_page_refs():
    """IDs outside the document root keep their normal ref behavior."""
    document_root = create_document_root(
        head_components=[Script.create(src="/probe.js")]
    )
    page_script = Script.create(src="/probe.js", id="page-probe")

    assert not document_root._get_all_hooks()
    assert page_script._get_all_hooks()
