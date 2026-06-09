# `rx.PerComponentState` — design

**Status:** Draft / iterating. No implementation yet beyond Phase 0.
**Branch:** `claude/focused-ramanujan-gglpnp`

A redesign of `rx.ComponentState` that (a) is immune to the production
state-name desync bug, (b) works inside `rx.foreach` (dynamic, runtime number
of instances), and (c) has a clean story for initializing per-instance state —
including from other states — at creation time.

## Problems being solved

| Issue | Summary |
|-------|---------|
| [#6616](https://github.com/reflex-dev/reflex/issues/6616) | `ComponentState` crashes the frontend in prod (`TypeError: d is not a function`) when its dynamically-generated state name desyncs between the compiled frontend and the backend. |
| [#3718](https://github.com/reflex-dev/reflex/issues/3718) | `ComponentState` can't be used in `rx.foreach` — all iterations share one state (compile-time states can't be created dynamically at runtime). |
| [#3771](https://github.com/reflex-dev/reflex/issues/3771) | No clean way to set initial values at `.create()` time (`cls.count = 5` replaces the Var and breaks the component). |
| [#5750](https://github.com/reflex-dev/reflex/issues/5750) | Can't initialize a field from another state's Var (`Objects are not valid as a React child`). |
| [#5871](https://github.com/reflex-dev/reflex/issues/5871) | The documented `cls.__fields__["x"].default = ...` workaround is broken: subclasses share the same `Field`, so one instance's default leaks to all. |
| [#6629](https://github.com/reflex-dev/reflex/issues/6629) | (Discovered here) `get_var_value` silently returns wrong values for Var *operations*. Shapes the init design; see "Var handling". |

## Root cause of #6616 (reproduced)

`ComponentState.create()` names each per-instance state subclass with a
process-global counter:

```python
cls._per_component_state_instance_count += 1
state_cls_name = f"{cls.__name__}_n{cls._per_component_state_instance_count}"
```

In `reflex run --env prod`, the **build** process evaluates the page (counter
`0→1`, `context.js`/the bundle ship `..._n1`). The backend worker is then
**forked** from the build process (inheriting counter `=1`) and re-evaluates the
stateful page on startup → produces `..._n2`, leaving both registered. The
hydrate delta then references `..._n2`, which the frontend bundle has no
reducer for, so the socket `event` handler throws `dispatch[substate] is not a
function` (minified `d[y]`), as an unhandled promise rejection that breaks the
whole event loop. Confirmed end-to-end in a browser with the exact stack from
the issue.

## Phase 0 — shipped: crash guard (independent of the redesign)

`packages/.../web/utils/state.js` now skips (and `console.warn`s about) any
delta entry whose substate has no reducer, instead of crashing:

```js
for (const substate in update.delta) {
  if (typeof dispatch[substate] !== "function") { console.warn(...); continue; }
  dispatch[substate](update.delta[substate]);
  ...
}
```

Validated in a browser (unknown-substate delta → no unhandled rejection, event
loop keeps working). Regression test:
`tests/integration/tests_playwright/test_unknown_substate_delta.py`.
Commit `a81712eb`.

## Core model

One backend `State` subclass per `PerComponentState` definition, with a
**deterministic** name (from module + qualname — no counter). Per-instance data
lives in **dict fields keyed by a client id from React's `useId()`**:

- Each declared field `count: int = 0` is backed by a dict `count: dict[str, int]`
  plus the recorded default `0`.
- Each `@rx.var` is backed by a dict too (`doubled: dict[str, int]`), populated
  per-id.
- `get_component`'s output is wrapped as an `rx.memo` component, so every usage
  (including each `rx.foreach` iteration) is its own React component with its
  own stable `useId()`.

Inside the memo: `const _cid = useId()`. References compile to:
- var read: `cls.count` → `state.count[_cid] ?? <default>`
- event: `cls.increment` → `ReflexEvent("...increment", { cid: _cid })` (the id
  injected as a reserved payload key).

On the backend, a handler runs with `self` bound to a **`ScopedView(backing,
cid)`** proxy: `self.count` reads `backing.count.get(cid, default)` and
`self.count = v` writes `backing.count[cid] = v` (copy-on-write so the delta
system fires). `get_state`/async-context delegate to the backing instance.

**Why this fixes the bugs:** the single state name is deterministic
(frontend/backend can't disagree → #6616), and instance multiplicity is a
*runtime* dict key, not a compile-time class (→ #3718). Delta granularity is
field-level (whole dict per change), identical to today's `list[dict]`+foreach
workaround — no regression; optimizable later (Phase 3).

### Validated mechanics (experiments, dev + prod)

- Compiled memo emits `const _cid = useId()`, `counts_rx_state_?.[_cid]`, and
  `ReflexEvent("...increment", ({ ["cid"] : _cid }))`.
- Three counters via `rx.foreach`, fully independent + reactive; backend slots
  keyed by `useId` (`{"_r_0_":2,"_r_2_":1}` in dev; `{"_R_j2qj5_":...}` in a real
  prod build with prerender + minification). No JS errors.
- Backend `ScopedView`: handler body `self.count += 1` (no `cid` param) updates
  the right slot; `dirty_vars={'count'}`, delta `{'count_rx_state_': {...}}`.
- Per-scope computed vars: a mount-time register seeds defaults + initial
  computed values; recompute dependents per-cid after a handler; unmount frees
  the slot.
- Cleanup hook exists (`on_mount`/`on_unmount` useEffect lifecycle in component.py).

## API surface

```python
class Counter(rx.PerComponentState):
    count: int = 0
    label: str = ""

    @rx.var
    def doubled(self) -> int:
        return self.count * 2

    @rx.event
    def increment(self):                 # natural body; self is the per-instance slot
        self.count += 1

    @rx.event
    def on_mount(self, start_value: int = 0, label: str = ""):
        # runs on the backend right after this instance mounts; self is scoped.
        self.count = start_value
        self.label = label

    @classmethod
    def get_component(cls, **props):
        return rx.hstack(
            rx.text(cls.label), rx.text(cls.count), rx.text(cls.doubled),
            rx.button("+", on_click=cls.increment), **props,
        )

Counter.create(start_value=5, font_size="2em")                 # single instance
rx.foreach(Store.rows, lambda r: Counter.create(start_value=r.n))  # N instances
```

### Built-ins (reserved names)
- `is_mounted: bool` — per-instance, `False` until `on_mount` resolves. Gate UI
  that depends on backend-initialized values (especially Var-based init that has
  no static default): `rx.cond(cls.is_mounted, real_ui, rx.spinner())`.
- `on_mount(self, ...)` — optional; its parameters define the init contract.
- `on_unmount(self)` — optional; teardown / persist back to a parent. (confirm)

### `create()` routing rule (locked)
- `create(*children, **kwargs)` calls `get_component(cls, *children, **kwargs)` —
  normal Python binding (declare params explicitly, rest land in `**props`).
- Independently, `{k: kwargs[k] for k in on_mount.params if k in kwargs}` becomes
  the mount-event payload (values handled per "Var handling" below).
- An arg needed at both compile time (in `get_component`) and runtime (in
  `on_mount`) is simply **declared in both signatures**. `get_component` sees the
  live Var; `on_mount` gets the runtime value/reference.

## Initialization & Var handling

`.create()` wraps `get_component` in a `Fragment` and attaches an `on_mount`
lifecycle event. How each `on_mount`-matching arg is delivered depends on the
arg and the parameter annotation.

**By value** — `on_mount(self, x: int)`:
- Constant → baked as the frontend default (no flash) *and* delivered to
  `on_mount`. No round-trip.
- Provably-plain field/computed reference (incl. large vars and backend state) →
  resolved on the backend via `get_var_value` at mount. No round-trip.
- Anything else (composite, `rows[i]`, foreach-derived) → round-trips the
  evaluated value in the payload. Always-correct default; backend-resolution is
  the optimization layered on only when provably safe.

**By reference** — `on_mount(self, src: rx.Var[T])`:
- The handler receives an `rx.Var`, not a value. It can `self._src = src` (store
  the reference → live link) or `await self.get_var_value(src)` (snapshot now /
  on demand).
- Only valid for plain refs/literals; a composite/foreach-derived Var here is a
  **compile-time error** ("can't reference a composite Var on the backend — pass
  a value or a key").

### Reference-Var (why, and how it sidesteps #6629 + pickling)
- Arbitrary Vars **can't be pickled** (cast Vars like `StringCastedVar` are
  `__init_subclass__.<locals>` classes → `PicklingError`). So we don't pickle
  raw Vars.
- A by-reference arg is delivered as a small **reference-Var** we control that
  carries only `(state, field_name)` from the passed Var's **direct** `_var_data`.
  It pickles trivially into redis and resolves *correctly* via `get_var_value`
  (it is a genuine plain reference, so it avoids #6629 even before that's fixed).
- Compile-time check uses the **direct** `_var_data` (not the recursive
  `_get_all_var_data()`); if it isn't a plain ref/literal → compile error.

### `get_var_value` footgun (#6629)
`get_var_value` reads `_get_all_var_data()`, which recursively merges constituent
var-data, so an operation var inherits its first operand's `state`/`field_name`
and silently returns the wrong value (`State.a + State.b` → `1` not `3`;
`State.items[0]` → the whole list). Our reference-Var only ever wraps a plain
ref, so it's unaffected; the underlying bug is filed separately.

## Patterns

**Window into shared data** (live, no large round-trip, foreach-friendly): keep
data in a shared state, pass a small *key* (and optionally the source ref),
render the shared state windowed by the key.

```python
class RowCard(rx.PerComponentState):
    key: str = ""                                   # slot, for handler-side use

    @rx.event
    def on_mount(self, source: rx.Var[dict[str, Row]], key: str):
        self._source = source                       # reference-Var (picklable)
        self.key = key

    @classmethod
    def get_component(cls, source, key, **props):   # declared -> in scope at compile
        row = source[key]                           # live Var + key -> reactive windowed read
        return rx.text(row.name, **props)

rx.foreach(DataStore.row_ids,
           lambda rid: RowCard.create(source=DataStore.rows_by_id, key=rid))
```

Two faces of the same `(state, field)`: compile-time `get_component` uses the
**live Var** (fully reactive); runtime `on_mount` gets the **picklable
reference-Var**. For large collections, handlers should `get_state(...)` + index
by key rather than `get_var_value(whole_collection)`.

## Decisions log

- **D1** New primitive `rx.PerComponentState`; deprecate & redirect
  `ComponentState` onto it later (don't change `ComponentState` semantics first).
- **D2** Ship the #6616 crash guard now, separately. **(done — `a81712eb`)**
- **D3** v1 includes per-scope **computed vars**.
- **D4** Built-in `is_mounted` Var + default backend `on_mount` handler that
  receives the create-time props.
- **D5** `.create()` wraps `get_component` in a `Fragment` and attaches the
  `on_mount` lifecycle event built from inspected `on_mount` params.
- **D6** Routing rule: all `create()` args go to `get_component` (explicit params
  + `**props`); `on_mount` independently captures its matching params; dual-use
  args declared in both.
- **D7** Var init contract: by-value (round-trip default; backend-resolve
  optimization for provably-plain refs/literals) vs by-reference (`rx.Var`
  annotation → controlled reference-Var).
- **D8** By-reference requires a plain backend-resolvable ref/literal; composite
  or foreach-derived → compile error.
- **D9** Don't pickle arbitrary Vars; deliver/store by-reference args as a
  controlled picklable reference-Var carrying `(state, field)`.
- **D10** Allow passing an arbitrary shared-source ref (e.g.
  `DataStore.rows_by_id`) through `create`.
- **D11** File the `get_var_value` operation-var footgun separately. **(done —
  #6629)**

## Open questions / critique

- **O1 (identity).** `useId` ties an instance to its React *position*, not a data
  key. In `foreach`, whether per-instance state follows the *row* or the *slot*
  depends on the React `key` Reflex emits. Strong lean: support an optional
  explicit `key=` on `create()` that overrides `useId` (also the bridge to a
  future explicit-scope API). **Needs decision.**
- **O2 (mount race).** A user interaction before `on_mount` resolves mutates the
  default slot, then `on_mount` clobbers it. `on_mount` must be queued ahead of
  user events.
- **O3 (traffic).** Every mount/unmount is a backend event; a large `foreach`
  fires many `on_mount`s on load. Consider batching/debouncing registration.
- **O4 (delta granularity).** Whole-dict per change (= today's workaround).
  Phase 3: partial per-`cid` deltas + a smarter `applyDelta` merge.
- **O5 (generic write-through).** Writing back through a stored reference-Var to
  a shared state (a `set_var_value`-like capability) isn't designed yet.
- **O6 (SSR/prerender).** `useId` validated in a real prod build; document the
  initial-default/`is_mounted` behavior before backend init lands.
- **O7 (on_unmount).** Confirm we ship a symmetric optional `on_unmount`.

## Phased plan

- **Phase 0 — done.** #6616 crash guard + regression test.
- **Phase 1 — the `PerComponentState` primitive.** Backing-dict codegen,
  `ScopedClassProxy` (compile-time `cls.x`/`cls.handler` resolution),
  `ScopedView` (backend self), reserved `__scope_register`/`__scope_discard`
  handlers, `on_mount`/`is_mounted`, the Var init contract + reference-Var, allow
  the primitive in `foreach`, per-scope computed vars. Unit + Playwright tests
  (incl. prod). Docs.
- **Phase 2 — redirect `ComponentState`.** Reimplement on the new engine;
  deprecate external `.State`/handler/var access; migration notes.
- **Phase 3 — optimization/completeness.** Partial per-`cid` deltas; computed
  vars depending on external states; reconnect/GC; generic write-through (O5).
