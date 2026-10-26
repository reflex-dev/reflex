"""Unit tests for SSR compile output and configuration."""

from __future__ import annotations

import json

from pytest_mock import MockerFixture
from reflex_base.compiler.templates import app_root_template, context_template

import reflex as rx
from reflex.utils.frontend_skeleton import (
    _compile_package_json,
    _update_react_router_config,
)


def test_prod_command_ssr(mocker: MockerFixture):
    """With runtime_ssr=True, prod command is 'node ssr-serve.js'."""
    conf = rx.Config(app_name="test", runtime_ssr=True)
    mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)

    result = _compile_package_json()
    pkg = json.loads(result)

    assert pkg["scripts"]["prod"] == "node ssr-serve.js"


def test_prod_command_static(mocker: MockerFixture):
    """With runtime_ssr=False, no prod command is defined."""
    conf = rx.Config(app_name="test", runtime_ssr=False)
    mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)

    result = _compile_package_json()
    pkg = json.loads(result)

    assert "prod" not in pkg["scripts"]


def test_ssr_deps_only_when_enabled(mocker: MockerFixture):
    """SSR-specific deps are only installed when runtime_ssr=True."""
    ssr_only_deps = ("@react-router/express", "express", "compression")
    install_frontend_packages = mocker.patch(
        "reflex.app.js_runtimes.install_frontend_packages"
    )

    app = rx.App(theme=None)
    for ssr in (True, False):
        conf = rx.Config(app_name="test", runtime_ssr=ssr)
        mocker.patch("reflex.app.get_config", return_value=conf)
        app._get_frontend_packages({})
        install_set, _ = install_frontend_packages.call_args.args
        deps = {package.rpartition("@")[0] for package in install_set}
        for dep in ssr_only_deps:
            if ssr:
                assert dep in deps, f"{dep} should be present when runtime_ssr=True"
            else:
                assert dep not in deps, (
                    f"{dep} should NOT be present when runtime_ssr=False"
                )


def test_dev_and_export_commands_unchanged(mocker: MockerFixture):
    """Dev and export commands are the same regardless of runtime_ssr."""
    results = {}
    for ssr in (True, False):
        conf = rx.Config(app_name="test", runtime_ssr=ssr)
        mocker.patch("reflex.utils.frontend_skeleton.get_config", return_value=conf)
        results[ssr] = json.loads(_compile_package_json())

    assert results[True]["scripts"]["dev"] == results[False]["scripts"]["dev"]
    assert results[True]["scripts"]["export"] == results[False]["scripts"]["export"]


def test_ssr_true_in_config():
    """With runtime_ssr=True, config has ssr: true."""
    conf = rx.Config(app_name="test", runtime_ssr=True)
    result = _update_react_router_config(conf)

    parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
    assert parsed["ssr"] is True


def test_ssr_false_in_config():
    """With runtime_ssr=False, config has ssr: false."""
    conf = rx.Config(app_name="test", runtime_ssr=False)
    result = _update_react_router_config(conf)

    parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
    assert parsed["ssr"] is False


def test_ssr_with_prerender():
    """runtime_ssr and prerender can coexist."""
    conf = rx.Config(app_name="test", runtime_ssr=True)
    result = _update_react_router_config(conf, prerender_routes=True)

    parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
    assert parsed["ssr"] is True
    assert parsed["prerender"] is True


def test_default_ssr_is_false():
    """Default config has ssr: false."""
    conf = rx.Config(app_name="test")
    result = _update_react_router_config(conf)

    parsed = json.loads(result.removeprefix("export default ").removesuffix(";"))
    assert parsed["ssr"] is False


def _render_root(runtime_ssr: bool) -> str:
    """Render root template with minimal valid params.

    Args:
        runtime_ssr: Whether runtime SSR is enabled.

    Returns:
        Rendered template string.
    """
    return app_root_template(
        imports=[],
        custom_codes=[],
        hooks={},
        window_libraries=[],
        render={"contents": "children"},
        dynamic_imports=set(),
        runtime_ssr=runtime_ssr,
    )


def test_root_template_has_loader_when_ssr_true():
    """With runtime_ssr=True, root.jsx template contains the SSR loader."""
    result = _render_root(runtime_ssr=True)

    assert "export async function loader" in result
    assert "getBackendURL" in result
    assert "SSR_DATA" in result


def test_root_template_loader_checks_shell_gen_header():
    """The SSR loader short-circuits for shell generation requests."""
    result = _render_root(runtime_ssr=True)

    assert "x-reflex-shell-gen" in result
    assert "state: null" in result
    # isbot check should NOT be in the loader — bot routing is in ssr-serve.js.
    assert "isbot" not in result


def test_root_template_loader_forwards_query_string():
    """The SSR loader sends the query string along with the path."""
    result = _render_root(runtime_ssr=True)

    assert "path: pathname + search," in result


def test_root_template_no_loader_when_ssr_false():
    """With runtime_ssr=False, root.jsx template has no SSR loader."""
    result = _render_root(runtime_ssr=False)

    assert "export async function loader" not in result
    assert "getBackendURL" not in result


def test_context_template_has_ssr_state_when_ssr_true():
    """With runtime_ssr=True, context.js reads the root loader state."""
    result = context_template(
        initial_state={"test_state": {"field_rx_state_": "value"}},
        state_name="test_state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
        runtime_ssr=True,
    )

    assert 'useRouteLoaderData("root")' in result
    assert "ssrHydrated" in result
    assert "ssrState" in result


def test_context_template_no_ssr_state_when_ssr_false():
    """With runtime_ssr=False, context.js has no SSR-related code."""
    result = context_template(
        initial_state={"test_state": {"field_rx_state_": "value"}},
        state_name="test_state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
        runtime_ssr=False,
    )

    assert "useRouteLoaderData" not in result
    assert "ssrHydrated" not in result
    assert "ssrState" not in result


def test_context_template_ssr_store_uses_ssr_state():
    """With runtime_ssr=True, the state stores start from ssrState."""
    result = context_template(
        initial_state={"my_app.state": {"count_rx_state_": 0}},
        state_name="my_app.state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
        runtime_ssr=True,
    )

    assert "createStateStore({ ...initialState, ...ssrState })" in result
    assert "ssrState?.[substateName] ?? initialState[substateName]" in result


def test_context_template_static_store_no_ssr_state():
    """With runtime_ssr=False, the state stores use initialState directly."""
    result = context_template(
        initial_state={"my_app.state": {"count_rx_state_": 0}},
        state_name="my_app.state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
        runtime_ssr=False,
    )

    assert "createStateStore(initialState)" in result
    assert "store: serverStateStore" in result
    assert "ssrState" not in result
