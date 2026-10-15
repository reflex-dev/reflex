"""Regression tests for the generated context.js frontend template."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from reflex_base.compiler.templates import context_template

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")

# Stand-ins for the modules context.js imports, keyed by the specifier they
# replace. ``createElement`` returns a plain tree to walk, and every hook throws:
# the server provider must not need React's dispatcher at all.
_STUB_MODULES = {
    "react": """
const hook = (name) => () => {
  throw new Error(`${name} called while rendering on the server`);
};
export const useContext = hook("useContext");
export const useMemo = hook("useMemo");
export const useReducer = hook("useReducer");
export const useRef = hook("useRef");
export const useState = hook("useState");
export const useEffect = hook("useEffect");
export const useLayoutEffect = hook("useLayoutEffect");
export const createElement = (type, props, ...children) => ({
  type,
  props: { ...props, children: children.length === 1 ? children[0] : children },
});
""",
    "$/utils/state": """
export const applyDelta = () => {};
export const ReflexEvent = () => ({});
export const hydrateClientStorage = () => ({});
export const useEventLoop = () => [];
export const refs = {};
""",
    "$/utils/context-registry": """
export const ColorModeContext = {};
export const UploadFilesContext = {};
export const DispatchContext = {};
export const EventLoopContext = {};
export const getStateContext = () => ({});
export const registerApp = () => {};
export const eventLoop = {};
""",
    "@emotion/react": "export const jsx = () => null;\n",
}

# Renders ``StateProvider`` around a leaf and reports every level between them,
# outermost first: a component by name, or a context with whether its value is
# the one the server should provide.
_SERVER_RENDER_DRIVER = """
import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[2]).href);
const leaf = { leaf: true };
const levels = [];
let node = mod.StateProvider({ children: leaf });
while (node !== leaf) {
  if (typeof node.type === "function") {
    levels.push({ component: node.type.name });
    break;
  }
  if (node.type === mod.DispatchContext) {
    levels.push({ context: "DispatchContext" });
  } else {
    const name = Object.keys(mod.StateContexts).find(
      (key) => mod.StateContexts[key] === node.type,
    );
    levels.push({ context: name, value: node.props.value === mod.initialState[name] });
  }
  node = node.props.children;
}
process.stdout.write(JSON.stringify(levels));
"""


def _event_loop_provider_body() -> str:
    """Render context.js and return the ``EventLoopProvider`` function body.

    Returns:
        The source of the generated ``EventLoopProvider`` component.
    """
    rendered = context_template(
        is_dev_mode=False,
        default_color_mode="light",
        initial_state={"state": {}},
        state_name="state",
    )
    start = rendered.index("export function EventLoopProvider")
    end = rendered.index("const useIsomorphicLayoutEffect", start)
    return rendered[start:end]


def test_event_loop_provider_memoizes_its_element() -> None:
    """``EventLoopProvider`` must return a memoized provider element.

    ``useEventLoop`` subscribes to router state (``useLocation``,
    ``useNavigate``), so the provider re-renders on every navigation even
    though ``addEvents`` and ``connectErrors`` are stable. Returning the same
    element object keeps the context value stable, so unrelated router updates
    do not invalidate its consumers.
    """
    body = _event_loop_provider_body()

    assert re.search(r"return useMemo\(\s*\(\) =>\s*createElement\(", body), (
        "EventLoopProvider should return a useMemo'd createElement call."
    )
    assert "[addEventsLocal, connectErrors, children]" in body, (
        "EventLoopProvider's useMemo must depend on the dispatchers and children."
    )


def test_event_loop_provider_still_publishes_module_dispatchers() -> None:
    """The module-level dispatchers must be assigned outside the memo.

    JSX literals built outside the React-tree path reach ``addEvents`` through
    the module-level dispatchers, so those assignments have to run on every
    render, not only when the memoized element is recomputed.
    """
    body = _event_loop_provider_body()

    assign_index = body.index("eventLoop.addEvents = addEventsLocal;")
    memo_index = body.index("return useMemo(")
    assert assign_index < memo_index, (
        "module-level dispatchers must be published before the memoized return."
    )
    assert "eventLoop.connectErrors = connectErrors;" in body[:memo_index]


@requires_node
def test_server_state_provider_renders_one_context_per_substate(tmp_path: Path):
    """On the server, each substate adds exactly one level to the page render.

    React's server renderer recurses once per element level, so wrapping every
    substate's context in its own component doubled the depth of every page and
    overflowed the stack of apps with many substates.
    """
    names = ["reflex___state____state"] + [
        f"reflex___state____state__sub_{i}" for i in range(199)
    ]
    rendered = context_template(
        is_dev_mode=True,
        default_color_mode='"light"',
        initial_state={name: {"n": i} for i, name in enumerate(names)},
        state_name=names[0],
    )
    for specifier, source in _STUB_MODULES.items():
        stub = tmp_path / (specifier.replace("/", "_").replace("$", "") + ".mjs")
        stub.write_text(source)
        rendered = rendered.replace(f'from "{specifier}"', f'from "./{stub.name}"')
    module = tmp_path / "context.mjs"
    module.write_text(rendered)
    driver = tmp_path / "driver.mjs"
    driver.write_text(_SERVER_RENDER_DRIVER)

    result = subprocess.run(
        ["node", str(driver), str(module)],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    levels = json.loads(result.stdout)

    assert levels == [{"context": "DispatchContext"}] + [
        {"context": name, "value": True} for name in names
    ]
