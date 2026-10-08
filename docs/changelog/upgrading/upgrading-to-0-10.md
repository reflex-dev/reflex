---
title: "Upgrading to Reflex 0.10"
meta_description: "Changes to review when upgrading an app from Reflex 0.9 to 0.10, with the fix for each: backend vars read on a state class, class-level defaults, background tasks, and state stores shared with 0.9 instances."
---

# Upgrading to Reflex 0.10

This page covers the 0.10 changes most likely to break an existing app, or to be missed in the [changelog](/docs/changelog/), with the fix for each.

## Reading a backend var on a state class

Reading a backend var on the state class, such as `State._items`, now returns its `Field` instead of the var's default value ([#7312](https://github.com/reflex-dev/reflex/pull/7312)). Passing it to a component raises `ChildrenTypeError` (as a child) or `TypeError: Unsupported type <class 'reflex_base.vars.base.Field'> for LiteralVar` (as a prop), and interpolating it without a conversion in an f-string or with `str.format()` raises `BackendVarFormatError` (`!r`, `!s` and `str()` embed the `Field` text instead). Reading the var on a state instance, such as `self._items`, is unchanged.

Replace the class read with what the code meant:

| To use | Write |
| --- | --- |
| The default, baked into the page | `State._items.default_value()` |
| A constant shared by all sessions | Declare it as `ClassVar[...]`; the class read is the plain value, as on 0.9 |
| A value the UI shows and updates | A regular state var or a computed var |

```python
from typing import ClassVar

import reflex as rx


class State(rx.State):
    _items: list[str] = ["a", "b"]
    _endpoint: ClassVar[str] = "https://example.com/api"


def page():
    return rx.vstack(
        # 0.9: rx.foreach(State._items, rx.text) baked in the default.
        rx.foreach(State._items.default_value(), rx.text),
        rx.text(State._endpoint),
    )
```

`default_value()` does not exist on 0.9.x, where `State._items` is already the plain list and `State._items.default_value()` raises `AttributeError: 'list' object has no attribute 'default_value'`. A package that supports both versions can read the field through `get_fields()`, which works on both:

```python
State.get_fields()["_items"].default_value()
```

## Assigning a state var through its class

On 0.9, `State.count = 10` replaced the class attribute, but new instances still started at the declared default. In 0.10 a state var is a descriptor on its class, and assigning over it raises `TypeError` instead of breaking the var. This includes pytest's `monkeypatch.setattr` and `unittest.mock.patch.object` on a var. Change the default on the var's field, patch the field in tests, and declare class-level configuration as `ClassVar`:

```python
from typing import ClassVar
from unittest import mock

import httpx

import reflex as rx


class State(rx.State):
    count: int = 0
    _client: ClassVar[httpx.AsyncClient | None] = None


State.__fields__["count"].default = 10  # 0.9: State.count = 10
State._client = httpx.AsyncClient()  # a ClassVar stays an ordinary class attribute

with mock.patch.object(State.__fields__["count"], "default", 99):
    ...
```

[Changing Defaults](/docs/vars/base-vars/#changing-defaults) has the details, including mutable defaults and browser storage vars.

## Calling inherited handlers from background tasks

In a background task, `self` is a proxy that only allows changes inside `async with self`. A handler declared on the same state was already called through that proxy, but a handler inherited from a parent state was not: on 0.9, `self.inherited_handler()` ran on the parent state without the lock, so it could write outside `async with self`. In 0.10 it goes through the proxy like any other handler ([#7312](https://github.com/reflex-dev/reflex/pull/7312)):

- Outside `async with self`, a call that modifies state raises `ImmutableStateError`; a read-only handler still runs.
- Inside it, `self` in the called handler is the proxy, so `type(self)` is `StateProxy`. Use `self.__class__` to get the state class; `isinstance(self, Parent)` still works.

On 0.9 this background task wrote to the parent state without the lock; on 0.10 the first call raises `ImmutableStateError`:

```python
class Parent(rx.State):
    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


class Child(Parent):
    @rx.event(background=True)
    async def work(self):
        self.bump()  # Raises ImmutableStateError on 0.10.
```

Make the call inside `async with self`, which works on both versions:

```python
class Child(Parent):
    @rx.event(background=True)
    async def work(self):
        async with self:
            self.bump()
```

## Sharing a state store between 0.9 and 0.10 instances

Instances of 0.9 and 0.10 cannot share a Redis or disk state store. A 0.10
instance loads state saved by 0.9, but a 0.9 instance discards state saved by
0.10 and starts the session over, so a rolling deploy that runs both versions,
or a rollback to 0.9 against the same store, resets the sessions that reach the
older instance. Upgrade every instance of an app together, and clear the store
(or point the app at a fresh one) when rolling back. See
[Self Hosting](/docs/hosting/self-hosting/#production-mode) for how the state
store is shared between instances.

## Other changes

- `EventHandler.is_background` and `EventHandler.supersedes` are read once per handler ([#7370](https://github.com/reflex-dev/reflex/pull/7370)), so a decorator that marks a handler function with `rx.event.BACKGROUND_TASK_MARKER` or `rx.event.SUPERSEDES_MARKER` must run before the handler is first used. A mark set afterwards is ignored without a warning. `@rx.event(background=True)` and `@rx.event(supersedes=True)` set it in time.
- Assigning an undeclared attribute on a state, such as `self.typo = 1`, still raises `SetUndefinedStateVarError` in dev mode but no longer in prod ([#7312](https://github.com/reflex-dev/reflex/pull/7312)). In prod it sets a plain attribute that is not a var, so changes to it are not tracked and never reach the client.
- `reflex[db]` allows `sqlmodel` 0.0.45 and later ([#7462](https://github.com/reflex-dev/reflex/pull/7462)), which stores a plain `datetime` field as UTC and rejects naive values. See [Datetimes and SQLModel upgrades](/docs/database/tables/#datetimes-and-sqlmodel-upgrades) if your app stores naive datetimes.
