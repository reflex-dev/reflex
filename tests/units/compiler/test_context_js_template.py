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
# replace. Server tests fail if a client-only hook runs without a dispatcher.
_STUB_MODULES = {
    "react": """
const hook = (name) => () => {
  throw new Error(`${name} called while rendering on the server`);
};
export const useContext = hook("useContext");
export const useCallback = hook("useCallback");
export const useSyncExternalStore = hook("useSyncExternalStore");
export const useMemo = hook("useMemo");
export const useReducer = hook("useReducer");
export const useRef = hook("useRef");
export const useState = hook("useState");
export const useEffect = hook("useEffect");
export const useLayoutEffect = hook("useLayoutEffect");
export const createElement = (type, props, ...children) => ({
  type,
  props: {
    ...props,
    children: children.length
      ? children.length === 1 ? children[0] : children
      : props?.children,
  },
});
export const createContext = (value) => {
  const context = { defaultValue: value };
  context.Provider = context;
  return context;
};
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
export const StateStoreContext = { name: "StateStoreContext" };
StateStoreContext.Provider = StateStoreContext;
export const getStateContext = () => ({});
export const useStateContext = () => ({});
export const registerApp = () => {};
export const eventLoop = {};
""",
    "@emotion/react": "export const jsx = () => null;\n",
}

# Renders ``StateProvider`` around a leaf and resolves its fixed-depth wrapper.
_SERVER_RENDER_DRIVER = """
import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[2]).href);
const leaf = { leaf: true };
const levels = [];
let node = mod.StateProvider({ children: leaf });
while (node !== leaf) {
  if (typeof node.type === "function") {
    levels.push({ component: node.type.name });
    node = node.type(node.props);
  } else if (node.type === mod.DispatchContext) {
    levels.push({ context: "DispatchContext" });
    node = node.props.children;
  } else if (node.type === mod.StateStoreContext) {
    const store = node.props.value;
    levels.push({
      context: "StateStoreContext",
      first: store.getSnapshot(process.argv[3]),
      last: store.getSnapshot(process.argv[4]),
    });
    node = node.props.children;
  } else {
    throw new Error("unexpected provider in state tree");
  }
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
    end = rendered.index("function createStateStore", start)
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
def test_server_state_provider_depth_is_constant_for_many_substates(tmp_path: Path):
    """The server provider tree stays shallow as the state tree grows."""
    names = ["reflex___state____state"] + [
        f"reflex___state____state__sub_{i}" for i in range(4999)
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
        ["node", str(driver), str(module), names[0], names[-1]],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    levels = json.loads(result.stdout)

    assert levels == [
        {"component": "StateStoreProviders"},
        {
            "context": "StateStoreContext",
            "first": {"n": 0},
            "last": {"n": len(names) - 1},
        },
        {"context": "DispatchContext"},
    ]


@requires_node
def test_client_state_store_notifies_only_substate_subscribers(tmp_path: Path):
    """A client delta updates and notifies only the changed substate."""
    rendered = context_template(
        is_dev_mode=True,
        default_color_mode='"light"',
        initial_state={
            "reflex___state____state": {"value": 1},
            "reflex___state____state__sub": {"value": 2},
        },
        state_name="reflex___state____state",
        legacy_state_contexts={"reflex___state____state__sub"},
    ).replace("function ClientStateProvider", "export function ClientStateProvider")
    react_stub = """
let hookIndex = 0;
let hookStates = [];
const contextValues = new Map();
export const subscriptions = [];
export const useContext = (context) => contextValues.get(context);
export const useCallback = (fn) => fn;
export const useSyncExternalStore = (subscribe, getSnapshot) => {
  subscriptions.push(subscribe);
  return getSnapshot();
};
export const useMemo = (fn) => fn();
export const useState = (initial) => {
  const index = hookIndex++;
  hookStates[index] ??= typeof initial === "function" ? initial() : initial;
  return [hookStates[index], () => {}];
};
export const useEffect = () => {};
export const createContext = (defaultValue) => {
  const context = { defaultValue };
  context.Provider = context;
  return context;
};
export const createElement = (type, props, ...children) => ({
  type,
  props: {
    ...props,
    children: children.length
      ? children.length === 1 ? children[0] : children
      : props?.children,
  },
});
export const setContextValue = (context, value) => contextValues.set(context, value);
"""
    state_stub = """
export const applyDelta = (state, delta) => ({ ...state, ...delta });
export const ReflexEvent = () => ({});
export const hydrateClientStorage = () => ({});
export const useEventLoop = () => [];
export const refs = {};
"""
    registry_path = (
        Path(__file__).parents[3]
        / "packages/reflex-base/src/reflex_base/.templates/web/utils/context-registry.js"
    )
    registry_source = registry_path.read_text().replace(
        'from "react"', 'from "./react.mjs"'
    )
    for specifier, source in (
        ("react", react_stub),
        ("$/utils/state", state_stub),
        ("$/utils/context-registry", registry_source),
        ("@emotion/react", "export const jsx = () => null;\n"),
    ):
        stub = tmp_path / (
            "registry.mjs"
            if specifier == "$/utils/context-registry"
            else specifier.replace("/", "_").replace("$", "") + ".mjs"
        )
        stub.write_text(source)
        rendered = rendered.replace(f'from "{specifier}"', f'from "./{stub.name}"')
    module = tmp_path / "context.mjs"
    module.write_text(rendered)
    driver = tmp_path / "driver.mjs"
    driver.write_text(
        """
import * as react from "./react.mjs";
import * as registry from "./registry.mjs";
globalThis.document = {};
const mod = await import("./context.mjs");
const leaf = { leaf: true };
let node = mod.ClientStateProvider({ children: leaf });
node = node.type(node.props);
const storeElement = node;
const store = storeElement.props.value;
react.setContextValue(registry.StateStoreContext, store);
const first = registry.useStateContext("reflex___state____state");
const second = registry.useStateContext("reflex___state____state__sub");
const dispatchElement = storeElement.props.children;
const legacyElement = dispatchElement.props.children;
const legacyContext = legacyElement.type(legacyElement.props);
let firstNotifications = 0;
let secondNotifications = 0;
let legacyNotifications = 0;
react.subscriptions[0](() => firstNotifications++);
react.subscriptions[1](() => secondNotifications++);
react.subscriptions[2](() => legacyNotifications++);
store.dispatchers["reflex___state____state__sub"]({ value: 2 });
store.dispatchers["reflex___state____state__sub"]({});
const noOpIdentityPreserved =
  store.getSnapshot("reflex___state____state__sub") === second;
const notificationsAfterNoOps = secondNotifications;
store.dispatchers["reflex___state____state__sub"]({ value: 3 });
const updated = registry.useStateContext("reflex___state____state__sub");
const updatedLegacyContext = legacyElement.type(legacyElement.props);
process.stdout.write(JSON.stringify({
  first,
  second,
  updated,
  legacyContext: legacyContext.props.value,
  updatedLegacyContext: updatedLegacyContext.props.value,
  legacyContextMatches: legacyContext.type === mod.StateContexts.reflex___state____state__sub,
  legacyNotifications,
  noOpIdentityPreserved,
  notificationsAfterNoOps,
  firstIdentityPreserved: store.getSnapshot("reflex___state____state") === first,
  firstNotifications,
  secondNotifications,
}));
"""
    )

    result = subprocess.run(
        ["node", str(driver)],
        capture_output=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "first": {"value": 1},
        "second": {"value": 2},
        "updated": {"value": 3},
        "legacyContext": {"value": 2},
        "updatedLegacyContext": {"value": 3},
        "legacyContextMatches": True,
        "legacyNotifications": 1,
        "noOpIdentityPreserved": True,
        "notificationsAfterNoOps": 0,
        "firstIdentityPreserved": True,
        "firstNotifications": 0,
        "secondNotifications": 1,
    }
