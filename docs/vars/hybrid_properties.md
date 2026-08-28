```python exec
import reflex as rx
from reflex.experimental import hybrid_property
```

# Hybrid Properties

A hybrid property derives a value from other vars using a **single method that works on
both the backend and the frontend**. It is defined with the `hybrid_property` decorator,
currently available as an experimental feature:

```python
from reflex.experimental import hybrid_property  # also exposed as rx._x.hybrid_property
```

When you reference a hybrid property in your UI, Reflex compiles it into a **client-side
var expression** built from the vars it reads — no extra data is created or sent. The same
method also works on the backend, where it behaves like a normal Python property.

Try typing in the inputs below — `full_name` updates on the client as you type:

```python demo exec id=hybrid_full_name
class NameState(rx.State):
    first_name: str = "Jane"
    last_name: str = "Doe"

    @rx.event
    def set_first_name(self, value: str):
        self.first_name = value

    @rx.event
    def set_last_name(self, value: str):
        self.last_name = value

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


def hybrid_full_name_example():
    return rx.vstack(
        rx.heading(NameState.full_name),
        rx.input(value=NameState.first_name, on_change=NameState.set_first_name),
        rx.input(value=NameState.last_name, on_change=NameState.set_last_name),
    )
```

Here `full_name` is rendered directly in the browser as `first_name + " " + last_name`.
Because it is a property, the **same** method is also available on the backend — inside an
event handler, `self.full_name` returns the actual combined string.

## Hybrid Properties vs. Computed Vars

[Computed vars](/docs/vars/computed-vars) and hybrid properties both derive a value from
other state vars, but they work very differently:

| | Computed var (`@rx.var`) | Hybrid property (`hybrid_property`) |
| --- | --- | --- |
| Where the value is produced | On the **server** | On the **client** when rendered (and on the server when accessed there) |
| Data sent to the browser | The result is **cached and sent** as an extra field of state | **Nothing extra** — compiles to a client-side expression over existing vars |
| Best suited for | Values only the server can produce: database lookups, secrets, heavy or `async` work | **Reformatting data already on the client**: combining fields, building labels, formatting |

A computed var effectively **duplicates** data: Reflex computes the value on the server,
stores it in your state, ships it to the browser, and keeps it in sync. That is exactly
what you want when the value depends on something only the server has.

A hybrid property adds **no** extra state. `NameState.full_name` above renders as an
expression over `first_name` and `last_name` that already live on the client, so there is
nothing extra to store, cache, or transmit. Reach for a hybrid property when you simply
need to **reshape existing frontend data** for display, and for a computed var when the
value can only be produced on the server.

## Separate Frontend Implementation

By default a hybrid property reuses the **same code** on the frontend and backend. When
the two should differ, register a frontend-only implementation with `@<name>.var`. The
function receives the state class and returns a [Var](/docs/vars/base-vars); declaring it
a `classmethod` types that first parameter as the class:

```python demo exec id=hybrid_greeting
class GreetState(rx.State):
    name: str = ""

    @rx.event
    def set_name(self, value: str):
        self.name = value

    @hybrid_property
    def greeting(self) -> str:
        # Backend (plain Python) implementation.
        return f"Hello, {self.name}!" if self.name else "Hello!"

    @greeting.var
    @classmethod
    def greeting(cls) -> rx.Var[str]:
        # Frontend (Var) implementation.
        return rx.cond(cls.name, f"Hello, {cls.name}!", "Hello!")


def hybrid_greeting_example():
    return rx.vstack(
        rx.heading(GreetState.greeting),
        rx.input(value=GreetState.name, on_change=GreetState.set_name),
    )
```

Repeating the property's name keeps its type visible when you access it on the class. If
you would rather not shadow the declaration, give the function a name of its own — the
result binds back to the property it was created from, and the extra name is removed from
the class:

```python
    @greeting.var
    @classmethod
    def _greeting_var(cls) -> rx.Var[str]:
        return rx.cond(cls.name, f"Hello, {cls.name}!", "Hello!")
```

What decides between the two is whether the attribute keeps the **function's own name**.
Assigning the result elsewhere (`short = greeting.var(fn)`) forks an independent property
under that name instead of binding back to `greeting` — unless `fn` happens to be named
`short` too, which is indistinguishable from the decorator form.

Because the frontend expression is built only from data that reaches the client, a hybrid
property's frontend logic may reference regular vars but **not backend-only vars** (those
prefixed with `_`). Reading a backend var while building the frontend value raises an
error — produce such values on the server with a computed var instead.

A var function may also return `None` to declare that the property has **no** frontend
value on that class, for example when it depends on configuration the class does not
enable. Class-level access then yields `None` instead of a var, and reaching the property
through an object var raises an error.

## Setters and Deleters

Like a plain property, a hybrid property accepts a `setter` and a `deleter`. They are
**backend-only** — the frontend value is derived from other vars, so there is nothing to
assign to on the client:

```python
class NameState(rx.State):
    first_name: str = "Jane"
    last_name: str = "Doe"

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @full_name.setter
    def _set_full_name(self, value: str):
        self.first_name, self.last_name = value.split(" ", 1)
```

Inside an event handler, `self.full_name = "Ada Lovelace"` runs that setter, which updates
`first_name` and `last_name` — and those, being real vars, are what the frontend re-renders
from.

## Nested Objects

Hybrid properties also work when defined on a dataclass, Pydantic model, or SQLAlchemy
model that is used as a var. Accessing the property through the object var renders it just
like accessing it on the state directly:

```python
from dataclasses import dataclass


@dataclass
class Info:
    first_name: str
    last_name: str

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ProfileState(rx.State):
    info: Info = Info(first_name="Jane", last_name="Doe")


# Renders as `info.first_name + " " + info.last_name` on the client:
rx.text(ProfileState.info.full_name)
```
