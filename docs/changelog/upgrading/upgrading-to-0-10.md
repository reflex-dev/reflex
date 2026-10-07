---
title: "Upgrading to Reflex 0.10"
meta_description: "Changes to review when upgrading an app from Reflex 0.9 to 0.10, with the fix for each: backend vars read on a state class, class-level defaults, background tasks, and state stores shared with 0.9 instances."
---

# Upgrading to Reflex 0.10

This page covers the 0.10 changes most likely to break an existing app, or to be missed in the [changelog](/docs/changelog/), with the fix for each.

## Reading a backend var on a state class

Reading a backend var on the state class, such as `State._items`, now returns its `Field` instead of the var's default value ([#7312](https://github.com/reflex-dev/reflex/pull/7312)). Passing it to a component raises `ChildrenTypeError` (as a child) or `TypeError: Unsupported type <class 'reflex_base.vars.base.Field'> for LiteralVar` (as a prop), and putting it in an f-string raises `BackendVarFormatError`. Reading the var on a state instance, such as `self._items`, is unchanged.

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

## Assigning a default through a state class

On 0.9, `State.count = 10` replaced the class attribute, but new instances still started at the declared default. In 0.10 it updates the var's default and the var stays a var ([#7461](https://github.com/reflex-dev/reflex/pull/7461)); [Changing Defaults](/docs/vars/base-vars/#changing-defaults) has the full rules. Check these before relying on it:

- It changes the default for values not yet stored on an instance, which includes every new session and `reset()`. A value already stored on an instance keeps it.
- The value must satisfy the var's annotation, or `TypeError: Invalid default for field` is raised. An unannotated var is typed from its default, so `_client = None` accepts only `None`; annotate the var with the type you assign.
- A zero-argument callable that the annotation does not accept, such as a function or a class, is called once during the assignment to check what it returns, then becomes the default factory. Do not assign something whose call has side effects.
- Mutable defaults are copied for every instance. A live client, lock or connection assigned to an `Any` or `Optional[...]` var is accepted, but reading the var on a new instance then raises `TypeError: cannot pickle '_thread.lock' object`. Declare an object that all sessions share as `ClassVar[...]`, which is never copied.
- Assigning on a mixin only affects states created afterwards. Do not assign defaults in event handlers, lifespan tasks, or at any other time after the app has started running: such an assignment only affects the worker process that ran it.

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
