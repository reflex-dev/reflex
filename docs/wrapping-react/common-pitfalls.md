---
title: Common Pitfalls - Wrapping React
---

# Common Pitfalls

Wrapping a simple display component usually just works. Wrapping an *interactive* library — editors, canvases, maps, charts with callbacks — has a handful of recurring failure modes. This page collects them, with the patterns that avoid each one. The examples use [React Flow](https://reactflow.dev), but every pitfall applies to any interactive library.

## High-frequency events flood the websocket

Interactive libraries fire some callbacks per animation frame: drag moves, pan/zoom updates, mouse moves, resize ticks. Wiring one of these directly to an event handler sends dozens of events per second to the backend, and the interaction becomes network-bound and laggy.

Three complementary fixes:

1. **Throttle or debounce** the handler with [event actions](/docs/events/event-actions/):

```python
react_flow(
    # At most one event per 50ms while dragging...
    on_nodes_change=State.on_nodes_change.throttle(50),
    # ...or only the final value after the burst stops.
    on_move_end=State.on_viewport_settled,
)
```

2. **Prefer the settled event** when the library offers a lifecycle (`onDrag` / `onDragStop`, `onMove` / `onMoveEnd`): bind your handler to the `*_end`/`*_stop` variant and skip the per-frame stream entirely. Throttling can drop the final event of a burst, so when you throttle a continuous stream, also bind the settled event to reconcile the authoritative final value.

3. **Keep payloads small**: forward the diff the library computed (e.g. React Flow's `changes` array) rather than the entire data structure, so each message is proportional to what changed.

Document per-frame triggers in your wrap's docstrings so users know which handlers need throttling.

## DOM events in payloads break serialization

Every argument an event spec forwards is JSON-serialized and sent to the backend. Many React callbacks pass a synthetic DOM event as the first argument — a huge, cyclic object that cannot be serialized. Forwarding it blindly breaks the trigger at runtime.

Write specs that drop the event and forward only plain data:

```python
def node_click_spec(
    event: rx.Var[dict[str, Any]], node: rx.Var[dict[str, Any]]
) -> tuple[rx.Var[dict[str, Any]]]:
    """(event, node) -> (node)."""
    return (node,)
```

If you need something *from* the event (like click coordinates for a context menu), project just those fields into a new object instead of forwarding the event:

```python
from reflex.vars import Var


def context_menu_spec(
    event: rx.Var[dict[str, Any]], node: rx.Var[dict[str, Any]]
) -> tuple[rx.Var[dict[str, Any]], rx.Var[dict[str, Any]]]:
    coords = Var(
        _js_expr=f"({{ clientX: {event}?.clientX, clientY: {event}?.clientY }})"
    ).to(dict)
    return (node, coords)
```

The same technique applies to cyclic library objects (internal state snapshots, instance references): project them down to the few plain fields your handler needs. Python event handlers may accept *fewer* arguments than the spec provides, so adding an extra argument to a spec does not break existing handlers.

## Unstable props remount the component's children

Some libraries require certain props to be **referentially stable** across renders — the classic example is a mapping of custom sub-component types (React Flow's `nodeTypes`, editor plugin maps, chart renderer registries). If the prop is a fresh object on every render, the library sees a "new" value each time and remounts everything under it (React Flow logs error `002` for exactly this).

An inline dict compiled into JSX is recreated per render. The fix is to emit the mapping as a **module-level constant** via custom code and pass a reference to it:

```python
class ReactFlow(rx.NoSSRComponent):
    ...
    node_types: rx.Var[Any]

    @classmethod
    def create(cls, *children, **props):
        if isinstance(props.get("node_types"), dict):
            # Compile {"card": "CardNode"} to a module-level constant.
            entries = ", ".join(
                f'"{k}": memo({v})' for k, v in props["node_types"].items()
            )
            cls._node_types_code = f"const nodeTypes = {{ {entries} }};"
            props["node_types"] = Var(_js_expr="nodeTypes")
        return super().create(*children, **props)

    def add_imports(self):
        return {"react": ["memo"]}

    def _get_custom_code(self) -> str | None:
        return getattr(self, "_node_types_code", None)
```

Two refinements for production wraps:

- Wrap each entry in `React.memo` (as above) so custom sub-components only re-render when their own props change — without it, every state update re-renders every instance.
- If you generate the constant's name, derive it from a **content hash** of the mapping so the name is stable across hot reloads and identical mappings on one page deduplicate.

## Function-valued props

Some props are neither data nor event handlers — they are synchronous functions the library calls while rendering or validating, like `isValidConnection`, a per-item `getColor`, or a filter predicate. These **cannot** be Python event handlers: the library needs a return value immediately on the client, and a round-trip to the backend is not possible.

Pass them as JavaScript expressions:

```python
from reflex.vars import Var

react_flow(
    is_valid_connection=Var(
        _js_expr="(connection) => connection.source !== connection.target"
    ),
)
```

For a friendlier API, accept a plain string in `create()` and convert it — a string is unambiguous when the prop only accepts a function:

```python
@classmethod
def create(cls, *children, **props):
    if isinstance(props.get("is_valid_connection"), str):
        props["is_valid_connection"] = Var(_js_expr=props["is_valid_connection"])
    return super().create(*children, **props)
```

## Calling the library's imperative API

Many libraries expose an instance API alongside props — `fitView()`, `map.flyTo()`, `chart.exportImage()` — usually via a hook or a ref. Backend event handlers can drive these with [`rx.call_script`](/docs/api-reference/browser-javascript/) if the instance is reachable from `window`. The pattern:

1. Capture the instance with a tiny custom-code component rendered inside your wrap, registering it in a global:

```python
class InstanceCapture(rx.Component):
    """Publishes the library instance to window for call_script access."""

    tag = "InstanceCapture"

    def add_imports(self):
        return {"@xyflow/react": ["useReactFlow"], "react": ["useEffect"]}

    def _get_custom_code(self) -> str:
        return """
function InstanceCapture() {
  const instance = useReactFlow();
  useEffect(() => {
    window.__flow_instance = instance;
    return () => { delete window.__flow_instance; };
  }, [instance]);
  return null;
}
"""
```

2. Call methods on it from any event handler, with an optional callback for return values:

```python
class State(rx.State):
    @rx.event
    def zoom_to_fit(self):
        return rx.call_script(
            "window.__flow_instance?.fitView({ padding: 0.2, duration: 400 })"
        )

    @rx.event
    def save(self):
        return rx.call_script(
            "window.__flow_instance?.toObject()",
            callback=State.store_snapshot,
        )

    @rx.event
    def store_snapshot(self, snapshot: dict):
        self.snapshot = snapshot
```

`rx.call_script` resolves promises before invoking the callback, so async instance methods work the same way. If your wrap supports multiple instances per page, key the registry by an id prop (`window.__instances[props.flowId] = instance`).

## Missing stylesheet or zero-height parent

The two classic "the component renders but looks broken/blank" bugs:

- Many libraries require a CSS file. Import it from the component itself (`add_imports` with the `""` key, see [imports and styles](/docs/wrapping-react/imports-and-styles/)) so it is impossible to forget.
- Canvas-style components usually fill their **parent** element. Mounted into an unsized parent, they render 0 pixels tall. Document that the parent needs a real `height`, and consider setting a sensible default style.

## SSR, hydration, and browser-only APIs

Components that measure the DOM, use `window`/`document`, or render from client-only sources (camera, canvas, WebGL) fail or mismatch when server-side rendered. Subclass `rx.NoSSRComponent` for the *root* component of such libraries — see [Dynamic Imports](/docs/wrapping-react/library-and-tags/).

Subcomponents that render inside the root usually do not need `NoSSRComponent` themselves; keeping them as plain `rx.Component` also lets them be used inside memoized custom components.

## Check the upstream package before wrapping

Before investing in a wrap:

- **Pin the version** (`library = "some-lib@1.2.3"`). Everything about a wrap — prop names, event signatures, CSS paths — is coupled to the upstream version.
- **Check for deprecation and renames.** Packages get superseded (`reactflow` → `@xyflow/react`, `react-beautiful-dnd` → unmaintained); wrapping the deprecated name means building on a frozen API with known bugs.
- **Prefer the library's controlled/uncontrolled modes deliberately.** If the backend only *observes* the component, use the uncontrolled mode (e.g. `defaultValue`-style props) and persist only the settled events — every interaction then costs zero websocket traffic. Reserve fully controlled props for when the backend must be the source of truth.

## Props with reserved or hyphenated names

Two prop-name gotchas:

- Names like `style`, `id`, or `key` are reserved by Reflex; wrap them under a different name and map back with `_rename_props` (see the [React PDF example](/docs/wrapping-react/more-wrapping-examples/)).
- Some libraries accept literally hyphenated props like `'aria-label'`. A snake_case prop compiles to camelCase (`ariaLabel`), which the library silently ignores. Use `_rename_props` to emit the hyphenated form:

```python
class Controls(rx.Component):
    ...
    aria_label: rx.Var[str]

    _rename_props = {"ariaLabel": "aria-label"}
```

Silent prop-name mismatches are the hardest wrapping bugs to notice — when a prop seems to have no effect, inspect the compiled JSX in `.web/` and compare against the library's TypeScript definitions.
