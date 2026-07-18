"""Server-side rendering (SSR) support for Reflex apps.

This module is the single home for everything SSR-specific so the rest of the
codebase stays SSR-agnostic. It covers three concerns:

* Backend: the ``/_ssr_data`` endpoint that computes the hydrated initial state
  for a route (reusing the regular event machinery).
* Compiler: the JS snippets injected into the ``app`` root and ``context``
  templates when SSR is enabled.
* Build/serve: dependencies, scripts, and packaging tweaks required to run a
  react-router SSR server in production.

Everything here is a no-op unless ``config.ssr_mode`` is not ``OFF``.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, path_ops, processes

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

    from reflex.app import App
    from reflex.config import Config
    from reflex.event import Event, EventHandler, EventSpec
    from reflex.state import BaseState

# Sentinel token/session id used for the stateless SSR render.
SSR_TOKEN = "__ssr__"


def is_enabled(config: Config | None = None) -> bool:
    """Whether SSR is enabled.

    Args:
        config: The config to read from, or the global config when omitted.

    Returns:
        True when ``config.ssr_mode`` is not ``OFF``.
    """
    config = config if config is not None else get_config()
    return config.ssr_mode != constants.SsrMode.OFF


# ---------------------------------------------------------------------------
# Backend: the /_ssr_data endpoint.
# ---------------------------------------------------------------------------


def _build_router_data(
    app: App, path: str, headers: dict[str, str], client_ip: str
) -> dict[str, Any]:
    """Build the ``router_data`` dict for a stateless SSR render.

    Args:
        app: The app, used to resolve the concrete path to a route pattern.
        path: The concrete request path (e.g. ``/blog/hello-world``).
        headers: The forwarded request headers.
        client_ip: The client IP address.

    Returns:
        A ``router_data`` dict with the same shape ``process()`` produces.
    """
    from reflex.route import extract_route_params

    resolved_route = app.router(path) or "404"
    params = extract_route_params(path, resolved_route)
    return {
        constants.RouteVar.PATH: "/" + resolved_route.removeprefix("/"),
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.QUERY: dict(params),
        constants.RouteVar.CLIENT_TOKEN: SSR_TOKEN,
        constants.RouteVar.SESSION_ID: SSR_TOKEN,
        constants.RouteVar.HEADERS: {
            "origin": headers.get("origin", headers.get("host", "http://localhost")),
            **headers,
        },
        constants.RouteVar.CLIENT_IP: client_ip,
    }


async def _process_ssr_event(state: BaseState, event: Event, path: str) -> None:
    """Run a single on_load event on the SSR state, swallowing errors.

    Handlers mutate the state instance in place; the yielded deltas are
    irrelevant since the whole tree is serialized afterwards.

    Args:
        state: The ephemeral root state instance.
        event: The event to process.
        path: The URL path (for error logging).
    """
    try:
        async for _update in state._process(event):
            pass
    except Exception:
        console.warn(f"SSR on_load handler failed for {path}: {traceback.format_exc()}")


async def _run_on_load_events(app: App, state: BaseState, path: str) -> None:
    """Run the route's on_load handlers on the ephemeral SSR state.

    Reuses the regular per-event executor (``state._process``) so on_load
    handlers run through the exact same code path as the websocket flow,
    correctly handling sync/async handlers, generators, and event chains.

    Args:
        app: The app to get load events from.
        state: The ephemeral root state instance.
        path: The URL path (for error logging).
    """
    from reflex.event import fix_events

    load_events = app.get_load_events(path)
    if not load_events:
        return

    events = fix_events(
        cast("list[EventSpec | EventHandler]", load_events),
        SSR_TOKEN,
        router_data=state.router_data,
    )
    for event in events:
        await _process_ssr_event(state, event, path)


def ssr_data(app: App):
    """Build the ``/_ssr_data`` endpoint handler.

    The handler creates an ephemeral state, applies route data, runs on_load
    handlers, and returns the serialized state tree for server-side rendering.

    Args:
        app: The app to get SSR data for.

    Returns:
        The SSR data request handler.
    """
    from starlette.responses import Response

    from reflex.state import RouterData, State
    from reflex.utils import format

    async def ssr_data_handler(request: Request) -> Response:
        """Handle an SSR data request.

        Args:
            request: The Starlette request object.

        Returns:
            Response with the serialized state as JSON.
        """
        body = await request.json()
        path = body.get("path", "/")
        headers = body.get("headers", {})

        if not app._state:
            return Response(
                content='{"state": null}',
                media_type="application/json",
            )

        # Ephemeral root state — no persistent session is created.  Use State
        # (root) rather than app._state which may be a subclass whose inherited
        # vars can't be set without a parent.
        state = State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]

        router_data = _build_router_data(
            app,
            path,
            headers,
            request.client.host if request.client else "0.0.0.0",
        )
        # Assigning router_data recomputes dependent DynamicRouteVars.
        state.router_data = router_data
        state.router = RouterData.from_router_data(router_data)

        await _run_on_load_events(app, state, path)

        json_str = format.json_dumps({"state": state.dict()})
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Cache-Control": "no-cache"},
        )

    return ssr_data_handler


# ---------------------------------------------------------------------------
# Compiler: JS snippets injected into the app root and context templates.
# ---------------------------------------------------------------------------

_APP_ROOT_LOADER = """
export async function loader({ request }) {
  // Short-circuit during static shell generation (no backend available).
  if (request.headers.get("x-reflex-shell-gen") === "1") {
    return { state: null };
  }
  // Fetch state data from the Python backend.  This loader runs in two cases:
  // (a) Full SSR render for bots — ssr-serve.js routes bot requests here.
  // (b) .data requests for client-side navigation — React Router calls the
  //     loader to fetch route data as JSON for the next page.
  // Both cases need real state data from the backend.
  const backendUrl = getBackendURL(env.SSR_DATA);
  try {
    const res = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie") ? { "Cookie": request.headers.get("cookie") } : {}),
      },
      body: JSON.stringify({
        path: new URL(request.url).pathname,
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
"""


def app_root_snippets(enabled: bool) -> dict[str, str]:
    """SSR snippets for the app root template.

    Args:
        enabled: Whether SSR is enabled.

    Returns:
        A dict of snippet strings keyed by their template placeholder.
    """
    if not enabled:
        return {
            "imports": 'import { Outlet } from "react-router";',
            "loader": "",
            "layout_head": "",
            "state_provider_props": "{}",
        }
    return {
        "imports": (
            'import { Outlet, useLoaderData } from "react-router";\n'
            'import { getBackendURL } from "$/utils/state";\n'
            'import env from "$/env.json";'
        ),
        "loader": _APP_ROOT_LOADER,
        "layout_head": (
            "  const loaderData = useLoaderData();\n"
            "  const ssrState = loaderData?.state || null;\n"
        ),
        "state_provider_props": "{ssrState}",
    }


def context_snippets(enabled: bool) -> dict[str, str]:
    """SSR snippets for the context template.

    Args:
        enabled: Whether SSR is enabled.

    Returns:
        A dict of snippet strings keyed by their template placeholder.
    """
    if not enabled:
        return {
            "ssr_context_export": "",
            "event_loop_ssr_hook": "",
            "event_loop_ssr_arg": "",
            "state_provider_arg": "",
            "state_provider_open": "",
            "state_provider_close": "",
        }
    return {
        "ssr_context_export": "\nexport const SSRContext = createContext(false);",
        "event_loop_ssr_hook": "\n  const ssrHydrated = useContext(SSRContext)",
        "event_loop_ssr_arg": "\n    ssrHydrated,",
        "state_provider_arg": ", ssrState = null",
        "state_provider_open": "createElement(SSRContext.Provider, {value: !!ssrState},",
        "state_provider_close": ")",
    }


def state_reducer_initial(state_name: str, enabled: bool) -> str:
    """The reducer initial value expression for a state slice.

    Args:
        state_name: The state slice name.
        enabled: Whether SSR is enabled.

    Returns:
        A JS expression for the ``useReducer`` initial value.
    """
    if enabled:
        return (
            f'ssrState !== null && ssrState["{state_name}"] != null '
            f'? ssrState["{state_name}"] : initialState["{state_name}"]'
        )
    return f'initialState["{state_name}"]'


# ---------------------------------------------------------------------------
# Build / serve helpers.
# ---------------------------------------------------------------------------


def react_router_ssr(config: Config | None = None) -> bool:
    """Value for the ``ssr`` field of react-router.config.js.

    Args:
        config: The config to read from, or the global config when omitted.

    Returns:
        True when SSR is enabled.
    """
    return is_enabled(config)


def prod_command(config: Config | None = None) -> str | None:
    """The production ``prod`` npm script command when SSR is enabled.

    Args:
        config: The config to read from, or the global config when omitted.

    Returns:
        The SSR prod command, or None to use the default static server.
    """
    if not is_enabled(config):
        return None
    return constants.PackageJson.Commands.PROD_SSR


def extra_dependencies(config: Config | None = None) -> dict[str, str]:
    """Additional npm dependencies required when SSR is enabled.

    Args:
        config: The config to read from, or the global config when omitted.

    Returns:
        A dict of dependency name to version (empty when SSR is off).
    """
    if not is_enabled(config):
        return {}
    return dict(constants.PackageJson.SSR_DEPENDENCIES)


# Scripts copied verbatim from the web template into the .web root when SSR is on.
_SSR_SCRIPTS = ("ssr-serve.js", "generate-shell.mjs")

# Source directories that live only in the .web root (not build/) and must be
# excluded when zipping an SSR frontend for deployment.
_ZIP_EXCLUDE_DIRS = frozenset(
    {"node_modules", "app", "utils", "styles", "components", "backend", "public"}
)


def zip_exclude_dirs() -> frozenset[str]:
    """Directory names to exclude when zipping an SSR frontend.

    Returns:
        The set of directory names to exclude.
    """
    return _ZIP_EXCLUDE_DIRS


def copy_scripts(web_dir: Path) -> None:
    """Copy the SSR runtime scripts into the .web directory.

    Args:
        web_dir: The .web directory to copy the scripts into.
    """
    import shutil

    for filename in _SSR_SCRIPTS:
        src = constants.Templates.Dirs.WEB_TEMPLATE / filename
        if src.exists():
            shutil.copy2(str(src), str(web_dir / filename))


def generate_shell(web_dir: Path) -> None:
    """Generate the static SPA shell (build/client/index.html) after an SSR build.

    Runs generate-shell.mjs, which renders the app with a normal user-agent so
    the loader returns empty state, and writes the resulting HTML.  The prod
    server serves this file to non-bot users for zero SSR overhead.

    Args:
        web_dir: The .web directory.
    """
    shell_script = web_dir / "generate-shell.mjs"
    if not shell_script.exists():
        console.warn("generate-shell.mjs not found, skipping SPA shell generation.")
        return

    console.info("Generating SPA shell for non-bot users...")
    node_path = str(path_ops.get_node_path() or "node")
    shell_process = processes.new_process(
        [node_path, "generate-shell.mjs"],
        cwd=web_dir,
        shell=constants.IS_WINDOWS,
    )
    shell_process.wait()
    if shell_process.returncode != 0:
        console.warn(
            "SPA shell generation failed.  Non-bot users will fall back to SSR."
        )
    else:
        console.info("SPA shell generated successfully.")
