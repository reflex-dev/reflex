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


def _apply(text: str, *edits: tuple[str, str]) -> str:
    """Apply text replacements whose old text occurs exactly once.

    Args:
        text: The text to edit.
        *edits: (old, new) pairs, applied in order.

    Returns:
        The edited text.
    """
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


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


SSR_ROOT_LOADER = """
export async function loader({ request }) {
  // Short-circuit during static shell generation (no backend available).
  if (request.headers.get("x-reflex-shell-gen") === "1") {
    return { state: null };
  }
  // Fetch the page's state from the Python backend for a server render.
  const backendUrl = getBackendURL(env.SSR_DATA);
  const { pathname, search } = new URL(request.url);
  try {
    const res = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie") ? { "Cookie": request.headers.get("cookie") } : {}),
      },
      body: JSON.stringify({
        path: pathname + search,
        headers: Object.fromEntries(request.headers),
      }),
    });
    if (res.ok) {
      return res.json();
    }
  } catch (e) {
    console.error("SSR data fetch failed:", e);
  }
  return { state: null };
}

// The client reads the loader's state only on mount and the live session runs
// on_load, so client-side navigations skip the loader instead of running the
// page's on_load handlers a second time on the backend.
export function shouldRevalidate() {
  return false;
}
"""


def test_root_template_ssr_loader():
    """With runtime_ssr=True, root.jsx exports the SSR loader and never revalidates it."""
    expected = _apply(
        _render_root(runtime_ssr=False),
        (
            "import { Outlet } from 'react-router';",
            (
                "import { Outlet } from 'react-router';"
                '\nimport { getBackendURL } from "$/utils/state";'
                '\nimport env from "$/env.json";'
            ),
        ),
        (
            "\n\nfunction ReflexProviders(",
            SSR_ROOT_LOADER + "\n\nfunction ReflexProviders(",
        ),
    )

    assert _render_root(runtime_ssr=True) == expected


def test_root_template_ssr_off_is_default():
    """With runtime_ssr=False, root.jsx is the template's default output."""
    assert _render_root(runtime_ssr=False) == app_root_template(
        imports=[],
        custom_codes=[],
        hooks={},
        window_libraries=[],
        render={"contents": "children"},
        dynamic_imports=set(),
    )


def _render_context(runtime_ssr: bool) -> str:
    """Render the context template for a single-substate app.

    Args:
        runtime_ssr: Whether runtime SSR is enabled.

    Returns:
        Rendered template string.
    """
    return context_template(
        initial_state={"my_app.state": {"count_rx_state_": 0}},
        state_name="my_app.state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
        runtime_ssr=runtime_ssr,
    )


def test_context_template_ssr_state():
    """With runtime_ssr=True, the stores and event loop start from the root loader's state."""
    expected = _apply(
        _render_context(runtime_ssr=False),
        (
            'import { jsx } from "@emotion/react";\n',
            (
                'import { jsx } from "@emotion/react";'
                '\nimport { useRouteLoaderData } from "react-router"\n'
            ),
        ),
        (
            "\nexport { ColorModeContext,",
            """
// State the backend rendered for this request (see the root loader), or null
// when the static SPA shell was served.
const useSSRState = () => useRouteLoaderData("root")?.state ?? null;

export { ColorModeContext,""",
        ),
        (
            "  const dispatch = useContext(DispatchContext)\n",
            (
                "  const dispatch = useContext(DispatchContext)"
                "\n  const ssrHydrated = useSSRState() !== null\n"
            ),
        ),
        ("    clientStorage,\n  )", "    clientStorage,\n    ssrHydrated,\n  )"),
        (
            "  const [store] = useState(() => createStateStore(initialState));",
            (
                "  const ssrState = useSSRState();"
                "\n  const [store] = useState(() => "
                "createStateStore({ ...initialState, ...ssrState }));"
            ),
        ),
        (
            (
                "  return createElement(StateStoreProviders, "
                "{ children, store: serverStateStore });"
            ),
            (
                "  const ssrState = useSSRState();"
                "\n  return createElement(StateStoreProviders, { children, store: "
                "{ ...serverStateStore, getSnapshot: (substateName) => "
                "ssrState?.[substateName] ?? initialState[substateName] } });"
            ),
        ),
    )

    assert _render_context(runtime_ssr=True) == expected


def test_context_template_ssr_off_is_default():
    """With runtime_ssr=False, context.js is the template's default output."""
    assert _render_context(runtime_ssr=False) == context_template(
        initial_state={"my_app.state": {"count_rx_state_": 0}},
        state_name="my_app.state",
        client_storage=None,
        is_dev_mode=False,
        default_color_mode='"system"',
    )
