---
title: "Upgrading to Reflex 0.11"
meta_description: "Changes to review when upgrading an app from Reflex 0.10 to 0.11, with the fix for each: event decorators, production origin checks, set vars, client state, the ASGI app and alembic migrations."
---

# Upgrading to Reflex 0.11

This page covers the 0.11 changes most likely to break an existing app, or to be missed in the [changelog](/docs/changelog/), with the fix for each. Several of the replacements, such as `config.frontend_url`, `SetVar.to_array()` and `rx.client_state`, do not exist on 0.10.x, so change that code in the same commit that upgrades Reflex.

## Decorators on event handlers

`@rx.event` now returns the `EventHandler` itself instead of the function it decorates ([#7673](https://github.com/reflex-dev/reflex/pull/7673)). A decorator stacked above `@rx.event` therefore receives the handler rather than the method. Such a method still runs and registers under its own name until 1.0, but 0.11 logs a deprecation warning:

```python
import functools

import reflex as rx


def logged(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        print(f"calling {fn.__name__}")
        return fn(self, *args, **kwargs)

    return wrapper


class State(rx.State):
    count: int = 0

    @logged  # Deprecated: `@logged` is applied above `@rx.event`.
    @rx.event
    def increment(self):
        self.count += 1
```

Apply other decorators below `@rx.event`, which works on 0.10 too:

```python
class State(rx.State):
    count: int = 0

    @rx.event
    @logged
    def increment(self):
        self.count += 1
```

The same change affects `@rx.event` outside a state:

- On a method of a class that is not a state, or on a `staticmethod` or `classmethod`, `@rx.event` leaves the method unchanged and warns. Remove the decorator. Calling such a method through its class, as in `Helper.compute(obj, 3)`, is not supported.
- On a module-level function whose first parameter is not annotated with a state class, it leaves a plain function and warns. Remove the decorator from helper functions. A [decentralized event handler](/docs/events/decentralized-event-handlers/), such as `def reset(state: MyState)`, is unchanged.
- Applying it to a handler that is already bound to a state, as in `ping = rx.event(OtherState.ping)`, raises `TypeError`. Decorate the function instead.
- Stacking `@rx.event` twice applies both, and the outer decorator's options win.
- Code that read attributes of the decorated function, such as markers set by your own decorators, finds the function at the handler's `.fn`.

## Values returned by event handlers

On 0.10 a handler could return only `None`, an event or a list of events, and any other value raised `TypeError`. In 0.11 a handler may return any value ([#7673](https://github.com/reflex-dev/reflex/pull/7673), [#7782](https://github.com/reflex-dev/reflex/pull/7782), [#7821](https://github.com/reflex-dev/reflex/pull/7821)):

- Backend code that awaits the handler, such as `total = await type(self).add(5)` in another handler, receives the value. See [Awaiting Event Handlers](/docs/events/chaining-events/#awaiting-event-handlers).
- When an event trigger such as `on_click` runs the handler, a value that is not an event is dropped, and in dev mode a warning names the handler once. Such values are not sent to the frontend. Returned events still chain: a returned `rx.redirect("/")` still runs in the browser.

A return value that can only be a mistaken event still raises `TypeError`, naming the handler: a bound handler such as `self.target` instead of `type(self).target`, an uncalled event creator such as `rx.redirect`, a coroutine, or a list that mixes events with other values. Yielded values must still be events.

```python
class State(rx.State):
    total: int = 0

    @rx.event
    def target(self): ...

    @rx.event
    def add(self, amount: int) -> int:
        self.total += amount
        return (
            self.total
        )  # 0.10 raised TypeError; 0.11 returns it to an awaiting caller.

    @rx.event
    def go_home(self):
        return (
            rx.redirect
        )  # Raises TypeError: "Did you mean to call it: rx.redirect(...)?"

    @rx.event
    def chain(self):
        return self.target  # Raises TypeError.
```

Call the event creator, and reference other handlers through the class:

```python
class State(rx.State):
    @rx.event
    def target(self): ...

    @rx.event
    def go_home(self):
        return rx.redirect("/")

    @rx.event
    def chain(self):
        return type(self).target
```

`self.handler()` still calls the handler's function directly, as on 0.10.

## Origin checks in production

In prod mode the backend now accepts browser requests only from its own origin and from `deploy_url`, which defaults to `None` instead of `http://localhost:3000` ([#7641](https://github.com/reflex-dev/reflex/pull/7641), [#7799](https://github.com/reflex-dev/reflex/pull/7799)). On 0.10 any origin was allowed. With `deploy_url` unset, the backend sends no CORS headers, so browsers cannot read cross-origin responses, and the event websocket accepts a connection only when its `Origin` matches the request's `Host`. With `deploy_url` set, that origin is accepted as well. Dev mode still allows any origin.

| Deployment | Action |
| --- | --- |
| Single-port `reflex run --env prod`, where the backend serves the frontend | None |
| Behind a TLS-terminating proxy that passes the original `Host` | None |
| Frontend on another origin: `--frontend-only` and `--backend-only`, a CDN, or a static host serving `reflex export` output | Set `REFLEX_DEPLOY_URL` on the backend to the frontend's public URL, scheme included |
| Proxy that rewrites `Host` and sends the original as `X-Forwarded-Host`, such as Azure Front Door | Set `trusted_proxy_hops`, for example `REFLEX_TRUSTED_PROXY_HOPS=1` |
| Proxy that rewrites `Host` without `X-Forwarded-Host` | Pass the original `Host` (nginx: `proxy_set_header Host $http_host;`), or set `REFLEX_DEPLOY_URL` on the backend |
| Frontend reachable from several origins | Set `cors_allowed_origins` to every accepted origin. An explicit list replaces the backend's own origin, so include it when the backend also serves the frontend, or use `["*"]` |

For a split frontend and backend:

```bash
REFLEX_DEPLOY_URL=https://app.example.com reflex run --env prod --backend-only
REFLEX_API_URL=https://api.example.com reflex run --env prod --frontend-only
```

`X-Forwarded-Host` and `X-Forwarded-Proto` count only when `trusted_proxy_hops` is set, and a trusted `X-Forwarded-Proto: https` also rejects pages served over plain http. The first websocket each worker rejects logs a warning that names the rejected origin and the setting to change. To restore the 0.10 behavior, set `cors_allowed_origins=["*"]`. See [CORS](/docs/advanced-onboarding/configuration/#cors) and [Self Hosting](/docs/hosting/self-hosting/#production-mode) for the details.

## Reading the deploy URL in app code

Because `deploy_url` now defaults to `None`, code that builds URLs from `config.deploy_url` produces text such as `None/reset` when it is unset. Use `config.frontend_url` for the frontend's origin: it is `deploy_url` when set, and `http://localhost:<frontend_port>` otherwise. When the backend serves the frontend from its own origin, as in single-port `--env prod`, use `config.api_url` for the app's public origin.

```python
import reflex as rx

config = rx.config.get_config()

# 0.10: "http://localhost:3000/reset" when deploy_url was unset.
# 0.11: "None/reset".
reset_link = f"{config.deploy_url}/reset"
```

```python
reset_link = f"{config.frontend_url}/reset"
```

## Set and frozenset vars

A `set` or `frozenset` state var is now a `SetVar` instead of an `ArrayVar` ([#7642](https://github.com/reflex-dev/reflex/pull/7642)). Sets have no order, so the list operations on it are deprecated: indexing, slicing, `map`, `filter`, `join`, `reverse`, `+`, `*`, the comparisons `<`, `<=`, `>` and `>=`, and `contains` with a `field`. They still compile with a deprecation warning until 1.0. Call `.to_array()` first:

```python
class State(rx.State):
    tags: set[str] = {"python", "reflex"}


rx.text(State.tags.join(", "))  # Deprecated: a set is not a sequence.
rx.text(State.tags.to_array().join(", "))
```

`rx.foreach` accepts a set var directly. `SetVar` adds set operations such as `union`, `intersection` and `issubset`; see [Set Operations](/docs/vars/var-operations/#set-operations).

## Browser storage vars with a default factory

Declare an `rx.Cookie`, `rx.LocalStorage` or `rx.SessionStorage` var with a storage value as its default, or with a storage type annotation ([#7582](https://github.com/reflex-dev/reflex/pull/7582)). On 0.10 a `default_factory` on such a var was ignored, or turned the var into an ordinary state var. In 0.11 the app fails to compile with `VarTypeError: Browser storage var 'State.theme' cannot use a default_factory`:

```python
class State(rx.State):
    theme: str = rx.field(
        default_factory=lambda: rx.LocalStorage("light", name="theme")
    )
```

The storage key and options must be known when the app compiles, so give the storage value as the default:

```python
class State(rx.State):
    theme: str = rx.LocalStorage("light", name="theme")
```

See [Browser Storage](/docs/api-reference/browser-storage/).

## Properties of Pydantic models and dataclasses

Reading a plain `@property` of a Pydantic model or a dataclass through a state var now raises `VarAttributeError` when the page compiles ([#7648](https://github.com/reflex-dev/reflex/pull/7648)). The property was never sent to the frontend, so on 0.10 the var always rendered empty:

```python
import pydantic


class User(pydantic.BaseModel):
    first: str = ""
    last: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class State(rx.State):
    user: User = User()


rx.text(State.user.full_name)  # Raises VarAttributeError.
```

For a Pydantic model, declare the property with `@pydantic.computed_field`, which includes it in the serialized state:

```python
class User(pydantic.BaseModel):
    first: str = ""
    last: str = ""

    @pydantic.computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"
```

For a dataclass, register an `rx.serializer` that includes the value:

```python
import dataclasses


@dataclasses.dataclass
class Point:
    x: int = 0

    @property
    def double(self) -> int:
        return self.x * 2


@rx.serializer
def serialize_point(point: Point) -> dict:
    return {"x": point.x, "double": point.double}
```

## Printing a backend var on a state class

A backend var read on the state class, such as `State._secret`, is a `Field` since 0.10. In 0.11, `print()`, logging and `str()` of it raise `BackendVarFormatError`, as f-strings already did ([#7651](https://github.com/reflex-dev/reflex/pull/7651)). The same error replaces the `TypeError` or `ValueError` raised when the var is passed where a frontend value is needed, such as a component prop, `rx.toast(State._secret)`, or the `title`, `description` or `image` of `app.add_page(...)`.

```python
class State(rx.State):
    _secret: str = ""


print(State._secret)  # Raises BackendVarFormatError.
print(repr(State._secret))  # Field(default='', ...)
print(State._secret.default_value())  # The default value.
```

Use `repr()` to print or log the field in server code. Reading the var on a state instance, such as `self._secret`, is unchanged. [Upgrading to Reflex 0.10](/docs/changelog/upgrading/upgrading-to-0-10/#reading-a-backend-var-on-a-state-class) lists the replacements for a backend var used in the UI.

## Client state

`rx.client_state` replaces `rx._x.client_state` ([#6936](https://github.com/reflex-dev/reflex/pull/6936), [#7804](https://github.com/reflex-dev/reflex/pull/7804)). The `rx._x` version keeps its argument order and warns until 1.0. In the new API, naming a var makes it global, and an unnamed var belongs to the outermost page or `@rx.memo` that uses it, so `global_ref` is gone:

| 0.10 | 0.11 |
| --- | --- |
| `rx._x.client_state("query", "")` | `rx.client_state("", name="query")` |
| `rx._x.client_state("open", False, global_ref=False)` | `rx.client_state(False)` |
| `ClientStateVar.create(...)` from `reflex.experimental.client_state` | `rx.client_state(...)` |
| `query.set_value` and `query.set_value("x")` | `query.set` and `query.set("x")` |

A legacy var created without a name was still global. If other pages or the backend read it, give its replacement a `name`.

```python
query = rx.client_state("", name="query")

rx.input(value=query.value, on_change=query.set)
```

A `name` must be an ASCII identifier, a letter or underscore followed by letters, digits or underscores, without `$`. This now applies to `rx._x.client_state` too, which raises `ValueError` for a name such as `"my-query"`. Declaring one name with two different defaults fails the compile with an error naming both declarations. See [Naming And Scoping Client State](/docs/wrapping-react/overview/#naming-and-scoping-client-state).

## Removed admin dashboard

The built-in starlette-admin dashboard is removed ([#7739](https://github.com/reflex-dev/reflex/pull/7739)). `rx.AdminDash(...)` and `rx.App(admin_dash=...)` raise `AdminDashRemovedError`:

```python
app = rx.App(admin_dash=rx.AdminDash(models=[User]))
```

Install `starlette-admin` and mount it yourself with `api_transformer`. Always give it an `AuthProvider`: without one, the dashboard serves read and write access to every table. The [admin dashboard guide](/docs/database/admin-dashboard/) has the full example, including the provider and a table mapping each `rx.AdminDash` argument:

```python
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin, ModelView

from reflex.model import get_engine

# MyAuthProvider and secret_key as defined in the admin dashboard guide.
admin_app = Starlette()
admin = Admin(
    get_engine(),
    auth_provider=MyAuthProvider(),
    secret_key=secret_key,
    middlewares=[Middleware(SessionMiddleware, secret_key=secret_key)],
)
admin.add_view(ModelView(User))
admin.mount_to(admin_app)

app = rx.App(api_transformer=admin_app)
```

## The ASGI app and API transformers

Calling an `rx.App` instance, `app()`, returns a plain ASGI callable instead of a `Starlette` app ([#7624](https://github.com/reflex-dev/reflex/pull/7624)). The result has no `add_middleware`, `routes` or `mount`:

```python
asgi = app()
asgi.add_middleware(MyMiddleware)  # AttributeError on 0.11.
```

Add Starlette middleware and routes to an app that you pass as [`api_transformer`](/docs/api-routes/overview/). Reflex mounts its own routes inside it, so its middleware covers them too:

```python
from starlette.applications import Starlette

api = Starlette()
api.add_middleware(MyMiddleware)

app = rx.App(api_transformer=api)
```

Apps passed to `api_transformer` now receive ASGI lifespan events, so the `lifespan`, `on_startup` and `on_shutdown` handlers of a FastAPI or Starlette transformer run, and a transformer whose startup raises stops the server from starting. Check these after upgrading:

- If you worked around the missing lifespan by also registering the transformer's lifespan with `app.register_lifespan_task`, remove that registration: it now runs the lifespan twice.
- The `starlette_app` argument of a lifespan task is now the `Starlette` app that serves Reflex's own routes. Code that searched its routes for the transformer no longer finds it.
- Raw ASGI middleware returned by a callable transformer now sees the `lifespan` scope, which has no `path`. Read `scope.get("path")` or check `scope["type"]` first. Middleware that raises on it keeps the lifespans inside it from running, and Reflex logs that the app appears not to support lifespan events.

See [Lifespan](/docs/api-routes/overview/#lifespan).

## Database migrations

The `reflex db` commands now run through alembic and the app's `alembic/env.py` ([#7742](https://github.com/reflex-dev/reflex/pull/7742), [#7809](https://github.com/reflex-dev/reflex/pull/7809)). `reflex db init` installs an `env.py` that loads the app and reads `db_url` from `rxconfig.py`, and `reflex db migrate`, `makemigrations` and `status` wrap `alembic upgrade head`, `alembic revision --autogenerate` and `alembic history --indicate-current`. See [Migrations](/docs/database/overview/#migrations).

### The env.py of an earlier release

Apps initialized by an earlier release have alembic's stock `env.py`, which earlier releases never ran. The next `reflex db` command, or `migrate()` call, replaces it with the current template and keeps the previous file as `alembic/env.old` (or `env.old.1`, and so on, if that name is taken). Existing revisions are kept, and no action is needed. Commit the new `env.py` and delete `env.old` once you no longer need it.

### A hand-edited env.py

An `env.py` you edited by hand, one without the stock template's `target_metadata = None` line, is kept, and Reflex warns once that it is not the Reflex template. On 0.10 the `reflex db` commands ignored it. In 0.11 they execute it, so it must work on its own. A common failure is the placeholder URL in `alembic.ini`:

```text
Alembic failed with NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:driver
alembic/env.py is not the Reflex template: move it aside and run reflex db init to write the current template.
```

When it fails, `reflex run` logs the error and starts the app, and the `reflex db` commands exit with it. To adopt the template, move your file aside and run `reflex db init`, which writes a missing `env.py` and keeps the existing revisions. Then copy any customizations you still need into the new file:

```bash
mv alembic/env.py alembic/env.py.custom
reflex db init
```

To keep your own file instead, make it take the database URL from `rxconfig.py`, after `config = context.config`:

```python
import reflex as rx

config.set_main_option("sqlalchemy.url", rx.config.get_config().db_url)
```

A custom `env.py` also lacks what the template adds: the models of the whole app, server defaults for added columns, and the warning for dropped tables.

### Model bases detected automatically

`rx.ModelRegistry.register(Base)` is now optional ([#7797](https://github.com/reflex-dev/reflex/pull/7797)). Until a base is registered, `reflex db` and the `alembic` command line migrate the tables of every `DeclarativeBase` subclass defined at module level, or in a class body, of a module the app imports. A base meant for another database, or one defined by an installed library, then gets `create_table` operations in the migrations for `db_url`. Register the bases of `db_url` to leave the others out:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AnalyticsBase(DeclarativeBase):
    """Tables of a separate analytics database."""


# Without this line, the next revision also creates AnalyticsBase's tables.
rx.ModelRegistry.register(Base)
```

Registering a SQLModel class, such as `rx.Model`, does not turn detection off. Review autogenerated revisions before applying them: one that drops tables now logs a warning naming them.

### Deprecated migration helpers

`reflex.model.alembic_autogenerate`, `reflex.model.get_migration_history` and `reflex.model.format_revision`, and the `rx.Model.alembic_autogenerate` and `rx.Model.get_migration_history` class methods, are deprecated and will be removed in 1.0. `alembic_autogenerate` now runs through `alembic/env.py` and ignores its `connection` argument. Use the `reflex db` commands, or their alembic equivalents:

| Deprecated | Replacement |
| --- | --- |
| `alembic_autogenerate()` | `reflex db makemigrations` or `alembic revision --autogenerate` |
| `get_migration_history()` | `reflex db status` or `alembic history --indicate-current` |
| `alembic_autogenerate(connection, write_migration_scripts=False)` to check for changes | `alembic check` |
| `format_revision(...)` | `reflex db status` |

### Other migration changes

- `reflex db migrate`, `makemigrations` and `status` report a missing `db_url` instead of failing inside alembic, and exit with status 1 when there is no database to migrate or it is not initialized. Scripts that run them where no database is configured may need a guard.
- `reflex db makemigrations` refuses to add a NOT NULL column whose only default is a dataclass `default_factory`, as in `mapped_column(default_factory=...)` on a `MappedAsDataclass` model, and names the column. Give the column a `server_default`, a literal `default=`, or make it nullable.
- `reflex db makemigrations` and the startup schema check evaluate every page first, so a model that only a page imports now appears in generated revisions.

## Upgrading reflex-enterprise

Upgrade reflex-enterprise to 0.9.12 together with Reflex 0.11. Its requirement on `reflex` does not move it forward on its own, so name both:

```bash
pip install -U "reflex==0.11.0" "reflex-enterprise==0.9.12"
```

0.9.12 fixes AG Grid API calls and `aligned_grids` failing with `ReferenceError: refs is not defined`, and the MCP OAuth consent redirect in dev. It also stops an `MCPPlugin` app from failing at `reflex run --env prod` startup now that `deploy_url` is unset by default. When the backend serves the frontend, the plugin's OAuth issuer and OpenAPI `servers` entry fall back to `api_url`, so set `REFLEX_API_URL`, or `MCPPlugin(issuer_url=...)`, to the app's public origin. `rxe.event(auth=..., rate_limit=...)` needs 0.9.11 or later on Reflex 0.11.

## Other changes

- A form control without a `name` still submits its value under its `id`, with a deprecation warning. The removal of that fallback moves from 0.11 to 0.12 ([#7789](https://github.com/reflex-dev/reflex/pull/7789)). Give each control a `name` before then.
- `rx.foreach` warns at compile time when an item with `on_mount`, `on_unmount` or hooks of its own is keyed by its index, the default ([#7820](https://github.com/reflex-dev/reflex/pull/7820)). After an item is removed, its `on_unmount` runs for the item at the last position. Set a unique, stable `key`, such as `key=item.id`, on the component the render function returns.
- In dev mode, Reflex warns when an event handler or other task blocks the event loop for longer than `event_loop_blocking_threshold` seconds, `0.2` by default ([#7672](https://github.com/reflex-dev/reflex/pull/7672)). Move blocking I/O to a thread or an async API, or set the threshold to `0` to turn detection off.
- In production, Granian replaces a backend worker that dies instead of stopping the server ([#7803](https://github.com/reflex-dev/reflex/pull/7803)). Set `GRANIAN_RESPAWN_FAILED_WORKERS=false` to keep the old behavior, for example when a process supervisor restarts the server.
- With the Redis state manager, the state changes a foreground handler made before it raised or was cancelled are now kept, as with the other state managers ([#7412](https://github.com/reflex-dev/reflex/pull/7412), [#7696](https://github.com/reflex-dev/reflex/pull/7696)). On 0.10 Redis discarded them.
- Generated pages no longer import the `refs` object from `$/utils/state`. Code that reads `refs[...]` in a raw `Var`, `rx.call_function` or an `add_hooks` string keeps working through a global, but `refs` is internal and may change without notice ([#7806](https://github.com/reflex-dev/reflex/pull/7806)). Act on a component by `id` with event actions such as `rx.set_value`, `rx.set_focus` and `rx.scroll_to`.
