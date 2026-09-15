"""Tests for reflex_base.compiler.templates."""

import re

from reflex_base.compiler import templates

# The unloaded-route throw block exactly as shipped in the pinned
# @react-router/dev runtime (dist/static/refresh-utils.mjs, enqueueUpdate).
_REFRESH_UTILS_THROW = """\
      let imported = window.__reactRouterRouteModuleUpdates.get(route.id);
      if (!imported) {
        throw Error(
          `[react-router:hmr] No module update found for route ${route.id}`,
        );
      }
      let routeModule = {
"""


def _render_vite_config() -> str:
    return templates.vite_config_template(
        base="/",
        hmr=True,
        force_full_reload=False,
        experimental_hmr=False,
        sourcemap=False,
    )


def test_vite_config_patches_react_router_hmr_runtime():
    """The generated vite config neutralizes react-router's unloaded-route throw.

    react-router's HMR client throws when an update batch includes a route the
    browser hasn't loaded, and the throw aborts the batch before the update
    queue is cleared — one edit to any not-currently-open page then poisons HMR
    until a full page reload. The generated config must ship a plugin that
    rewrites the served runtime to skip unloaded routes instead.
    """
    config = _render_vite_config()
    assert "patchReactRouterHmrRuntime()" in config
    assert '"\\0virtual:react-router/hmr-runtime"' in config

    # The embedded regex must match the pinned runtime's throw block, and the
    # replacement must drop the throw while keeping the update loop going.
    regex_match = re.search(r"const unloadedRouteThrow = /(.+)/;", config)
    assert regex_match is not None
    js_regex = regex_match.group(1)
    patched, n_subs = re.subn(
        js_regex, "if (!imported) continue;", _REFRESH_UTILS_THROW
    )
    assert n_subs == 1
    assert "throw" not in patched
    assert "if (!imported) continue;" in patched
