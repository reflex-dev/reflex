```python exec
import reflex as rx
```

# Memo

The `@rx.memo` decorator turns a function into a memoized React component. The compiler emits the function as its own module, and React's `memo` only re-renders it when its declared props change. Reach for it when a subtree is expensive to render and depends on a narrow slice of state.

## Requirements

Every parameter must be annotated with `rx.Var[...]` or `rx.RestProp`. The compiler reads those annotations to generate prop names, prop forwarding, and the JS function signature.

1. **`rx.Var[T]` for props** — annotate each prop as `rx.Var[T]` where `T` is the prop's runtime type (`str`, `int`, a TypedDict, etc.). Inside the function body, the parameter is a `Var` you compose into the rendered tree.
2. **`rx.RestProp` for spread props** — at most one parameter may be annotated as `rx.RestProp`, which forwards unrecognized kwargs through to the rendered root.
3. **`rx.Var[rx.Component]` for slot children** — a parameter named `children` annotated as `rx.Var[rx.Component]` accepts children rendered by the caller.
4. **Keyword arguments at the call site** — pass props by name, not by position.

Defaults need to be `rx.Var` values. For the common empty cases use the module-level constants `rx.EMPTY_VAR_STR` (an empty string), `rx.EMPTY_VAR_INT` (zero), and `rx.EMPTY_VAR_COMPONENT` (an empty component): `class_name: rx.Var[str] = rx.EMPTY_VAR_STR` falls back to `""` when the caller omits the prop, and `children: rx.Var[rx.Component] = rx.EMPTY_VAR_COMPONENT` makes a slot optional.

## Basic Usage

```python
class DemoState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1


@rx.memo
def expensive_component(label: rx.Var[str]) -> rx.Component:
    return rx.vstack(
        rx.heading(label),
        rx.text("This component only re-renders when props change."),
        rx.divider(),
    )


def index():
    return rx.vstack(
        rx.text(f"Count: {DemoState.count}"),
        rx.button("Increment", on_click=DemoState.increment),
        expensive_component(label="Memoized Component"),
    )
```

`expensive_component` re-renders only when `label` changes — bumping `DemoState.count` does not invalidate it.

## With State Variables

Props can be ordinary Vars. The memoized component re-renders when those Vars change:

```python
class AppState(rx.State):
    name: str = "World"


@rx.memo
def greeting(name: rx.Var[str]) -> rx.Component:
    return rx.heading("Hello, " + name)


def index():
    return rx.vstack(
        greeting(name=AppState.name),
        rx.input(value=AppState.name, on_change=AppState.set_name),
    )
```

## Forwarding Props with `rx.RestProp`

Use `rx.RestProp` to accept and forward arbitrary props (think `...rest` in JSX). Useful for thin wrappers that re-style a primitive without redeclaring every prop.

```python
@rx.memo
def primary_button(
    rest: rx.RestProp,
    *,
    label: rx.Var[str],
) -> rx.Component:
    return rx.button(label, rest, class_name="bg-primary-9 text-white")


def index():
    return primary_button(
        label="Save",
        on_click=rx.console_log("clicked"),
        id="save",
    )
```

At most one `rx.RestProp` parameter is allowed per memo.

The `rest` parameter should be treated as an opaque value and passed
positionally to any component which will use it.

You may use the `.merge` var operation to combine the arbitrary props with
another object Var or python dict. The memo body can read placeholders like
`rest.get("class_name", "")`, but the actual value will be unavailable at
compile time, so you can't branch on it or do python operations with the values,
only var operations which will be translated to Javascript expressions.

The same example as above, but now allowing the caller to optionally pass a
`class_name` that gets merged with the default styles:

```python
@rx.memo
def primary_button(
    rest: rx.RestProp,
    *,
    label: rx.Var[str],
) -> rx.Component:
    class_name = rest.get("class_name", "") + " bg-primary-9 text-white"
    return rx.button(label, rest.merge({"class_name": class_name}))
```


## Accepting Children

Declare a parameter named `children` typed as `rx.Var[rx.Component]` to receive a child subtree.

```python
@rx.memo
def card(
    children: rx.Var[rx.Component],
    *,
    title: rx.Var[str],
) -> rx.Component:
    return rx.box(
        rx.heading(title),
        children,
        class_name="border border-secondary-5 rounded-lg p-4",
    )


def index():
    return card(
        rx.text("Body copy goes here."),
        title="Memoized card",
    )
```

## Returning a `Var` Instead of a Component

A memo function can return `rx.Var[T]` instead of `rx.Component`. The compiler emits a plain JavaScript function and the call site is just a `Var` you can compose into the page.

```python
class PriceState(rx.State):
    amount: int = 100
    currency: str = "USD"


@rx.memo
def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
    return currency.to(str) + ": $" + amount.to(str)


def index():
    formatted = format_price(amount=PriceState.amount, currency=PriceState.currency)
    return rx.vstack(
        rx.text(formatted),
    )
```

The body of a `Var`-returning memo runs at compile time and is restricted to Var operations — no hooks, no Python branching on the Vars.

## Performance Considerations

Reach for `rx.memo` when:

- The component is expensive to render.
- Its output is a stable function of a small set of props.
- A frequently-updating ancestor would otherwise force it to re-render.

Skip it when:

- The component is cheap and the bookkeeping is not worth it.
- The props change on every render anyway — memo never gets to short-circuit.

## Migrating from the Old `rx.memo`

The previous `rx.memo` accepted plain-typed arguments (`def card(title: str)`). The new one requires `rx.Var[...]`. To migrate:

```python
# Before
@rx.memo
def card(title: str) -> rx.Component: ...


# After
@rx.memo
def card(title: rx.Var[str]) -> rx.Component: ...
```

The old `rx._x.memo` alias still resolves to the new memo and prints a one-time `was promoted to rx.memo` notice.

## API Reference

### `rx.memo`

```python
rx.memo(component_fn)
```

Wraps a function whose parameters are all `rx.Var[...]` or `rx.RestProp`. Returns a callable that constructs the memoized component (or a `Var` if the function's return annotation is `rx.Var[T]`).

| Argument | Type | Description |
| --- | --- | --- |
| `component_fn` | `Callable[..., rx.Component \| rx.Var]` | The function to memoize. All parameters must be `rx.Var[...]` or `rx.RestProp`. |
