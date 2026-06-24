"""Integration test for the frontend inspector compile + render pipeline.

End-to-end check that a real app, compiled with
``FrontendInspectorPlugin``, ends up with ``data-rx`` attributes on its
rendered DOM nodes that resolve to entries in ``source-map.json``. If any
link in the chain (``state.is_enabled`` → ``capture.capture`` → plugin
artifact writer → JSX emit) is broken, this test fails.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def InspectorApp():
    """Exercises three capture paths.

    - ``rx.foreach`` lambda body: one call site, many items, all shipped
      with the same ``data-rx`` (compile-time capture).
    - ``@rx.memo``: function body invoked at compile time, returned
      component captured and wrapped in a React memo at runtime.
    - ``@rx.var`` returning ``rx.Component``: the function body runs on
      the backend at request time, so its ``Component.create`` calls hit
      ``state.is_enabled()`` *after* the compile subprocess has exited —
      this is the exact dynamic-component path the state.py fallback
      exists to keep alive.
    """
    import reflex as rx

    class S(rx.State):
        items: list[str] = ["alpha", "beta", "gamma"]
        label: str = "dynamic_label"

        @rx.var
        def dynamic_card(self) -> rx.Component:
            return rx.box(rx.text(self.label), id="dynamic_card")

    @rx.memo
    def memo_panel(label: str) -> rx.Component:
        return rx.box(rx.text(label), id="memo_panel")

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.text("static", id="static_text"),
            rx.box(
                rx.foreach(S.items, lambda item: rx.text(item)),
                id="foreach_container",
            ),
            memo_panel(label="memo"),
            S.dynamic_card,
        )


@pytest.fixture(scope="module")
def inspector_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Run InspectorApp under AppHarness with FrontendInspectorPlugin active.

    Module-scoped: tests share one harness and one source-map.json. Per-test
    harnesses would import an ``inspectorapp`` module whose path differs
    from the cached ``sys.modules["inspectorapp"]`` entry, so source-map.json
    file fields would reference the *first* test's tmp dir.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        the running AppHarness instance.
    """
    from reflex_base.plugins.frontend_inspector import FrontendInspectorPlugin

    # AppHarness compiles the frontend via ``export(env=PROD)``, which would
    # otherwise deactivate the plugin via its env-mode gate. Force it active
    # so the test exercises the real capture + source-map.json + data-rx
    # emission path. Module-scoped MonkeyPatch since this fixture is too.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(FrontendInspectorPlugin, "_is_active", lambda _self: True)

    root = tmp_path_factory.mktemp("inspector_app")
    # AppHarness derives the app_name from the function name (lowercased,
    # double-underscores collapsed): "InspectorApp" → "inspectorapp".
    app_name = "inspectorapp"
    # ``templates.initialize_app`` short-circuits when rxconfig.py already
    # exists, so writing it here is how we inject the plugin. We also have
    # to pre-create the app package directory because the harness's skip
    # path doesn't run the template's directory bootstrap.
    (root / "rxconfig.py").write_text(
        "import reflex as rx\n"
        "from reflex_base.plugins.frontend_inspector import FrontendInspectorPlugin\n"
        "config = rx.Config(\n"
        f'    app_name="{app_name}",\n'
        "    plugins=[FrontendInspectorPlugin()],\n"
        ")\n"
    )
    (root / app_name).mkdir()
    (root / app_name / "__init__.py").write_text("")

    with AppHarness.create(root=root, app_source=InspectorApp) as harness:
        assert harness.app_instance is not None, "app failed to start"
        yield harness
    monkeypatch.undo()


def _source_map_path(harness: AppHarness) -> Path:
    from reflex_base import constants
    from reflex_base.inspector import PUBLIC_DIRNAME, SOURCE_MAP_FILENAME

    return (
        harness.app_path
        / constants.Dirs.WEB
        / constants.Dirs.PUBLIC
        / PUBLIC_DIRNAME
        / SOURCE_MAP_FILENAME
    )


def test_data_rx_attributes_resolve_in_source_map(
    inspector_app: AppHarness, page: Page
):
    """Every rendered ``data-rx`` value must map back to ``source-map.json``."""
    assert inspector_app.frontend_url is not None
    page.goto(inspector_app.frontend_url)

    expect(page.get_by_text("static")).to_be_visible()

    artifact = _source_map_path(inspector_app)
    assert artifact.is_file(), (
        f"source-map.json was not written to {artifact}; the inspector "
        "plugin did not run during compile"
    )
    source_map = json.loads(artifact.read_text())
    assert source_map, "source-map.json is empty"

    data_rx_values: list[str] = page.locator("[data-rx]").evaluate_all(
        "els => els.map(e => e.getAttribute('data-rx'))"
    )
    assert data_rx_values, (
        "no data-rx attributes in the rendered DOM — components were not "
        "captured or data-rx was not emitted"
    )

    missing = [cid for cid in data_rx_values if cid not in source_map]
    assert not missing, (
        f"{len(missing)} data-rx values have no source-map.json entry: "
        f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
    )


def test_foreach_items_share_source_map_entry(inspector_app: AppHarness, page: Page):
    """The ``rx.foreach`` lambda is one call site, so each rendered item must
    carry the *same* ``data-rx`` value and that value must be present in
    source-map.json.
    """
    assert inspector_app.frontend_url is not None
    page.goto(inspector_app.frontend_url)

    expect(page.get_by_text("alpha")).to_be_visible()

    item_cids: list[str | None] = page.locator(
        "#foreach_container [data-rx]"
    ).evaluate_all("els => els.map(e => e.getAttribute('data-rx'))")
    assert len(item_cids) >= 3, (
        f"expected at least 3 captured foreach items, got {len(item_cids)}: {item_cids}"
    )
    assert all(c is not None for c in item_cids), (
        "foreach items rendered without data-rx — dynamic capture failed"
    )
    assert len(set(item_cids)) == 1, (
        f"foreach items have different data-rx values {item_cids}; they "
        "share one call site so they must share one id"
    )

    source_map = json.loads(_source_map_path(inspector_app).read_text())
    assert item_cids[0] in source_map, (
        f"foreach item data-rx={item_cids[0]} is missing from source-map.json"
    )


def _find_line(app_module_path: Path, marker: str) -> int:
    """Find the 1-based line number containing ``marker`` in the app module.

    Args:
        app_module_path: Path to the generated app module file.
        marker: A unique substring to locate.

    Returns:
        The 1-based line number where ``marker`` first appears.

    Raises:
        AssertionError: If the marker is not present in the file.
    """
    for i, line in enumerate(app_module_path.read_text().splitlines(), start=1):
        if marker in line:
            return i
    msg = f"{marker!r} not found in {app_module_path}"
    raise AssertionError(msg)


def _assert_entry_points_at(
    source_map: dict,
    cid: str,
    *,
    app_module_path: Path,
    line: int,
    component: str,
):
    """The cid's source-map.json entry must point at the exact call site."""
    entry = source_map.get(cid)
    assert entry is not None, f"data-rx={cid} missing from source-map.json"
    assert entry["file"] == str(app_module_path.resolve()), (
        f"data-rx={cid} entry has file={entry['file']!r}, expected "
        f"{str(app_module_path.resolve())!r}"
    )
    assert entry["line"] == line, (
        f"data-rx={cid} entry has line={entry['line']}, expected {line} "
        f"(the line containing the {component} call in the app module)"
    )
    assert entry["component"] == component, (
        f"data-rx={cid} entry has component={entry['component']!r}, "
        f"expected {component!r}"
    )


def test_memo_component_entry_points_at_its_call_site(
    inspector_app: AppHarness, page: Page
):
    """``data-rx`` on a ``@rx.memo`` body must resolve to the exact line that
    created it — not just *some* entry in source-map.json. A click on the memo
    component in the browser overlay would otherwise open the wrong file or
    the wrong line.
    """
    assert inspector_app.frontend_url is not None
    page.goto(inspector_app.frontend_url)

    panel = page.locator("#memo_panel")
    expect(panel).to_be_visible()
    cid = panel.get_attribute("data-rx")
    assert cid is not None, "memo component rendered without data-rx"

    source_map = json.loads(_source_map_path(inspector_app).read_text())
    _assert_entry_points_at(
        source_map,
        cid,
        app_module_path=inspector_app.app_module_path,
        line=_find_line(inspector_app.app_module_path, 'id="memo_panel"'),
        component="Box",
    )


def test_dynamic_component_var_entry_points_at_its_call_site(
    inspector_app: AppHarness, page: Page
):
    """``data-rx`` on the ``@rx.var`` Component must resolve to the exact line
    that built it — proves the request-time capture in the worker hashes to
    the same id the compile pass wrote at that source location.
    """
    assert inspector_app.frontend_url is not None
    page.goto(inspector_app.frontend_url)

    card = page.locator("#dynamic_card")
    expect(card).to_be_visible()
    cid = card.get_attribute("data-rx")
    assert cid is not None, "dynamic component rendered without data-rx"

    source_map = json.loads(_source_map_path(inspector_app).read_text())
    _assert_entry_points_at(
        source_map,
        cid,
        app_module_path=inspector_app.app_module_path,
        line=_find_line(inspector_app.app_module_path, 'id="dynamic_card"'),
        component="Box",
    )
