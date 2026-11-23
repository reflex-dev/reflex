```python exec
import asyncio
from typing import Any
import reflex as rx
```

# Browser Javascript

Reflex compiles your frontend code, defined as python functions, into a Javascript web application
that runs in the user's browser. There are instances where you may need to supply custom javascript
code to interop with Web APIs, use certain third-party libraries, or wrap low-level functionality
that is not exposed via Reflex's Python API.

```md alert
# Avoid Custom Javascript

Custom Javascript code in your Reflex app presents a maintenance challenge, as it will be harder to debug and may be unstable across Reflex versions.

Prefer to use the Python API whenever possible and file an issue if you need additional functionality that is not currently provided.
```

## Executing Script

There are four ways to execute custom Javascript code into your Reflex app:

- `rx.script` - Injects the script via `next/script` for efficient loading of inline and external Javascript code. Described further in the [component library](/docs/library/other/script/).
  - These components can be directly included in the body of a page, or they may
    be passed to `rx.App(head_components=[rx.script(...)])` to be included in
    the `<Head>` tag of all pages.
- `rx.call_script` - An event handler that evaluates arbitrary Javascript code,
  and optionally returns the result to another event handler.

These previous two methods can work in tandem to load external scripts and then
call functions defined within them in response to user events.

The following two methods are geared towards wrapping components and are
described with examples in the [Wrapping React](/docs/wrapping-react/overview/)
section.

- `_get_hooks` and `_get_custom_code` in an `rx.Component` subclass
- `Var.create` with `_var_is_local=False`

## Inline Scripts

The `rx.script` component is the recommended way to load inline Javascript for greater control over
frontend behavior.

The functions and variables in the script can be accessed from backend event
handlers or frontend event triggers via the `rx.call_script` interface.

```python demo exec
class SoundEffectState(rx.State):
    @rx.event(background=True)
    async def delayed_play(self):
        await asyncio.sleep(1)
        return rx.call_script("playFromStart(button_sfx)")


def sound_effect_demo():
    return rx.hstack(
        rx.script(
            f'var button_sfx = new Audio("{rx.asset("vintage-button-sound-effect.mp3")}");'
            " function playFromStart(sfx) {sfx.load(); sfx.play()}"
        ),
        rx.button(
            "Play Immediately", on_click=rx.call_script("playFromStart(button_sfx)")
        ),
        rx.button("Play Later", on_click=SoundEffectState.delayed_play),
    )
```

## External Scripts

External scripts can be loaded either from the `assets` directory, or from CDN URL, and then controlled
via `rx.call_script`.

```python demo
rx.vstack(
    rx.script(
        src="https://cdn.jsdelivr.net/gh/scottschiller/snowstorm@snowstorm_20131208/snowstorm-min.js",
    ),
    rx.script("""
        window.addEventListener('load', function() {
            if (typeof snowStorm !== 'undefined') {
                snowStorm.autoStart = false;
                snowStorm.snowColor = '#111';
            }
        });
    """),
    rx.button("Start Duststorm", on_click=rx.call_script("snowStorm.start()")),
    rx.button("Toggle Duststorm", on_click=rx.call_script("snowStorm.toggleSnow()")),
)
```

## Accessing Client Side Values

The `rx.call_script` function accepts a `callback` parameter that expects an
Event Handler with one argument which will receive the result of evaluating the
Javascript code. This can be used to access client-side values such as the
`window.location` or current scroll location, or any previously defined value.

```python demo exec
class WindowState(rx.State):
    location: dict[str, str] = {}
    scroll_position: dict[str, int] = {}

    def update_location(self, location):
        self.location = location

    def update_scroll_position(self, scroll_position):
        self.scroll_position = {
            "x": scroll_position[0],
            "y": scroll_position[1],
        }

    @rx.event
    def get_client_values(self):
        return [
            rx.call_script("window.location", callback=WindowState.update_location),
            rx.call_script(
                "[window.scrollX, window.scrollY]",
                callback=WindowState.update_scroll_position,
            ),
        ]


def window_state_demo():
    return rx.vstack(
        rx.button("Update Values", on_click=WindowState.get_client_values),
        rx.text(f"Scroll Position: {WindowState.scroll_position.to_string()}"),
        rx.text("window.location:"),
        rx.text_area(value=WindowState.location.to_string(), is_read_only=True),
        on_mount=WindowState.get_client_values,
    )
```

```md alert
# Allowed Callback Values

The `callback` parameter may be an `EventHandler` with one argument, or a lambda with one argument that returns an `EventHandler`.
If the callback is None, then no event is triggered.
```

## Reaching Reflex from JavaScript

JavaScript you run in the browser reaches Reflex through `reflex`, an object
whose members stay the same across Reflex versions:

| Member | What it does |
| --- | --- |
| `reflex.ref(id)` | The ref of the component with that `id`. `undefined` until a component with that `id` renders; its `current` is `null` until React attaches the element, then the element. |
| `reflex.addEvents(events)` | Dispatch events, as an event trigger does. |
| `reflex.event(name, payload)` | Build an event for `reflex.addEvents`: `name` is the event handler's full name, `payload` its arguments by name. |
| `reflex.library(name)` | A promise of an npm library bundled for dynamic components, such as `"react"`. |

Prefer `reflex` over the other names a script can see, such as `refs`,
`ReflexEvent` or `addEvents`: those are internals of the frontend and may change
between Reflex versions.

### From a Script

Code run by `rx.call_script` sees `reflex`:

```python demo exec
class ReflexApiState(rx.State):
    result: str = ""

    @rx.event
    def set_result(self, result: str):
        self.result = result


def reflex_api_demo():
    return rx.vstack(
        rx.input(id="reflex_api_search", placeholder="Type something"),
        rx.hstack(
            rx.button(
                "Focus",
                on_click=rx.call_script(
                    "reflex.ref('reflex_api_search').current.focus()"
                ),
            ),
            rx.button(
                "Read",
                on_click=rx.call_script(
                    "reflex.ref('reflex_api_search').current.value",
                    callback=ReflexApiState.set_result,
                ),
            ),
            rx.button(
                "React version",
                on_click=rx.call_script(
                    "reflex.library('react').then((react) => react.version)",
                    callback=ReflexApiState.set_result,
                ),
            ),
        ),
        rx.text(f"Result: {ReflexApiState.result}"),
    )
```

### From a JavaScript Module

A JavaScript module, such as one a [wrapped component](/docs/wrapping-react/overview/)
imports, imports `reflex` from `$/utils/reflex`:

```javascript
import { reflex } from "$/utils/reflex";

export function saveSearch(handlerName) {
  const value = reflex.ref("reflex_api_search").current.value;
  reflex.addEvents([reflex.event(handlerName, { value })]);
}
```

### From Python

`rx.js` builds the same calls from Python. Each function returns a var, which
`rx.run_script` runs whether an event trigger uses it or an event handler
returns it:

| Python | JavaScript |
| --- | --- |
| `rx.js.ref(id)` | `reflex.ref(id)` |
| `rx.js.library(name)` | `reflex.library(name)` |

```python
class SearchState(rx.State):
    query: str = ""

    @rx.event
    def set_query(self, query: str):
        self.query = query

    @rx.event
    def read_search(self):
        # Read the input's current value from the browser.
        return rx.run_script(
            rx.js.ref("search").current.value, callback=SearchState.set_query
        )


def search():
    return rx.vstack(
        rx.input(id="search"),
        rx.button("Read", on_click=SearchState.read_search),
        rx.text(SearchState.query),
    )
```

Python has no `reflex.addEvents`: dispatch events from Python as usual, with an
event trigger or by returning them from an event handler. `reflex.addEvents` is
for JavaScript that sends a value it computed back to Python.

### Errors

Each error says what went wrong and how to fix it. The messages, with example
names:

```text
reflex.library("left-pad") cannot load "left-pad": the app does not bundle it for dynamic components. Bundle it by calling bundle_library("left-pad") from reflex.components.dynamic in your app's Python code.
```

```text
reflex.library("react") cannot load "react" yet: the app registers its bundled libraries when it first mounts, and it has not mounted. Call reflex.library from an event, such as on_mount or on_click, rather than while a module loads.
```

```text
reflex.library("$/utils/state") cannot load "$/utils/state": a name starting with "$/" is a module of the app's frontend, not a bundled npm library. Use reflex.ref, reflex.addEvents and reflex.event instead of Reflex internals, and import your own modules from a JavaScript module.
```

## JavaScript Modules

Write JavaScript in a `.js`, `.ts`, `.jsx` or `.tsx` file in your app's package
and import its exported functions in Python, like a Python module. Each function
returns an event: use it in an event trigger, or return or yield it from an
event handler.

```javascript
// my_app/scripts/party.js
import confetti from "canvas-confetti";
import { reflex } from "$/utils/reflex";

export function celebrate(count, elementId) {
  confetti({ particleCount: count });
  document.getElementById(elementId).scrollIntoView();
}

export function measure(id, handler) {
  const { width } = document.getElementById(id).getBoundingClientRect();
  reflex.addEvents([reflex.event(handler, { width })]);
}
```

```python
# my_app/my_app.py
import reflex as rx

from my_app.scripts.party import celebrate, measure


class PartyState(rx.State):
    count: int = 200
    width: float = 0

    @rx.event
    def finish(self):
        return celebrate(self.count, "results")

    @rx.event
    def set_width(self, width: float):
        self.width = width


def index():
    return rx.vstack(
        rx.button("Celebrate", on_click=celebrate(PartyState.count, "results")),
        rx.button("Finish", on_click=PartyState.finish),
        rx.button("Measure", on_click=measure("results", PartyState.set_width)),
        rx.text(f"Width: {PartyState.width}", id="results"),
    )


app = rx.App()
app.add_page(index)
```

Nothing is evaluated: the module is bundled with the app, and calling one of its
functions sends only the module's name, the function's name and the arguments.
Apps whose Content Security Policy forbids `unsafe-eval` can use them.

### Rules

- Only modules in your app's package import this way: the package that
  `app_name` in `rxconfig.py` names. A `.js` file in another package, such as
  a library you installed, is never imported.
- A Python module of the same name wins over a JavaScript one.
- Import each function by name, as in `from my_app.scripts.party import
  celebrate`, or use it on the module (`party.celebrate`).
  `from my_app.scripts.party import *` is not supported.
- When the app compiles, Reflex reads the module with the bundler's parser, so
  any JavaScript, TypeScript or JSX the bundler accepts works, and checks that
  each name you use from Python is an exported function. An export that may
  hold a function counts, such as `export const run = makeRunner()` or a name
  re-exported from another file. Python cannot call a value: an exported
  class or enum, or a `const` set to a literal, an object, an array or a class
  expression. A default export and TypeScript types are left out.
- A name used only inside an event handler is looked up when the handler runs,
  after the compile, so a wrong name there is reported in the browser.
- Arguments are sent as JSON. A var is sent as its value in the browser. An
  event handler arrives as its full name, which the function dispatches with
  `reflex.addEvents([reflex.event(name, payload)])`, as `measure` does above.
- The function's return value is not sent back. To get a value back, pass an
  event handler and dispatch it with the value, as `measure` does.
- The npm packages the module imports, such as `canvas-confetti`, are installed
  with the app. Pin a version with `frontend_packages` in `rxconfig.py`. Path
  aliases (`@/...`), subpath imports (`#...`) and specifiers with a scheme
  (`virtual:...`, `https://...`) are left to the bundler and not installed.
- Local files the module imports with relative paths, such as `./helpers.js`,
  `./party.css` or `./logo.png`, are bundled with it, and so are the files they
  import, including a stylesheet's `@import` and `url(...)` references. They
  must be inside your app's package directory, which is all of your project
  that is copied into the compiled app. A file imported as text
  (`./example.js?raw`), or a script imported as a URL (`./worklet.js?url`), is
  copied as it is, without the files it imports. A file that is a symbolic link
  is copied where the import names it, so the files it imports are found from
  there.

### Type Stubs

While you develop, Reflex writes a type stub next to each module the app
imports, `party.pyi` beside `party.js`, so type checkers resolve the import and
check each call. Argument types come from TypeScript annotations or, in a `.js`
file, JSDoc:

```javascript
// my_app/scripts/party.js
/**
 * @param {number} count
 * @param {string} elementId
 * @param {"left" | "right"} [side]
 */
export function celebrate(count, elementId, side) { /* ... */ }
```

gives this stub, shown without its imports and with each private alias, such
as `_float`, as the name it stands for:

```python
# my_app/scripts/party.pyi
def celebrate(
    count: float | Var[float],
    elementId: str | Var[str] | EventCallback[*tuple[Any, ...]],
    side: Literal["left", "right"] | Var[Literal["left", "right"]] = ...,
    /,
) -> EventSpec: ...
```

so `celebrate("lots", "results")` is a type error. Arguments are positional,
as JavaScript passes them, and each also takes a var, as does each item of a
list and each value of a mapping. A function reads its arguments as JSON, so
each type becomes the type of the JSON value Python sends:

| TypeScript or JSDoc | Python |
| --- | --- |
| `string` | `str`, or an event handler, sent as its name |
| `number` | `float` |
| `boolean` | `bool` |
| `null`, `undefined`, `void` | `None` |
| `"a" \| "b"`, `1 \| 2`, `true` | `Literal["a", "b"]`, `Literal[1, 2]`, `Literal[True]` |
| an enum | `Literal` of its values |
| `T[]`, `[T, U]` | `Sequence[T]`, `Sequence[T \| U]` |
| `Record<string, T>`, `{ [key: string]: T }` | `Mapping[str, T]` |
| an object type or interface of your own | `Mapping[str, Any]` |
| `A \| B` | the union of their types, `Any` if either is `Any` |
| no type, `any`, `unknown`, `object`, `bigint`, `A & B`, a type parameter | `Any` |
| a function, a class, `Date`, `Map`, `Set`, `Promise`, `HTMLElement` and other types of the browser or an npm package | `Any` |
| `x?: T`, or a default value | `x: T = ...`, when no required parameter follows |
| `...rest: T[]` | `*rest: T` |

The stub declares the functions the compile finds the module exports, as the
rules above count them; the names an `export * from "./more"` adds are not
among them, so re-export those by name (`export { go } from "./more"`) to
import them in a type-checked file. An overloaded function gets one
`@overload` per signature. A function TypeScript has no signature for, such as
`export const run = makeRunner()` when `makeRunner` has no types, takes any
arguments: `def run(*args: Any)`.

- Commit the stubs, so your editor and type checks in CI see them without
  running the app. A stub only changes when the types do: Reflex rewrites it
  when the module, a file it imports or reads types from (a `.d.ts` file,
  `import type`, a JSDoc `import("./types")`), the app's frontend packages or
  Reflex's stub generator changes. Writing a stub does not reload the backend.
  Delete a stub to have the next compile write it again.
- A file the types name that does not exist yet, such as `./shapes` in a JSDoc
  `import("./shapes")` before you create `shapes.d.ts`, is not watched: after
  you add it, delete the stub so the next compile reads the types again.
- Stubs are written only in development. `reflex export` and `reflex run --env
  prod` leave your source tree alone.
- Reflex only rewrites or removes a stub whose first line is its own
  `# Generated by Reflex from ...` header. A `.pyi` file without that line,
  such as one you write by hand, is yours: Reflex never changes or removes it.
- When the app stops importing a module, Reflex removes the stub it wrote for
  it.
- Reflex reads the types with TypeScript, which it installs with the app's
  frontend packages in development.
- Pyright reports a stub that has no Python module beside it as
  `reportMissingModuleSource`. Turn that rule off:

  ```toml
  # pyproject.toml
  [tool.pyright]
  reportMissingModuleSource = "none"
  ```

When the types cannot be read, the app still runs and Reflex warns
`Reflex could not read the argument types of the JavaScript modules
.../party.js, so their type stubs accept any arguments; the app still runs.`
The stub takes any arguments until the types can be read, and Reflex tries
again on every compile. The warning ends with one of these reasons:

- `script-signatures.js failed. If this repeats, delete .../.web/node_modules
  so that the next run reinstalls typescript, or report the error at
  https://github.com/reflex-dev/reflex/issues:` and TypeScript's error.
- `.../.web/script-signatures.js printed output that this version of Reflex
  does not read, so it is likely left over from another version.` Delete the
  `.web` directory, and the next run writes it again.

When a stub cannot be written, as in a read-only directory, the app still runs
and Reflex warns `Reflex could not write the type stub .../party.pyi:
Permission denied.` Make the directory writable, and the next compile writes
it. When it cannot remove the stub of a module the app no longer imports, it
warns `Reflex could not remove the type stub .../party.pyi, which it wrote for
a JavaScript module the app no longer imports`; delete the file yourself. When
it cannot read a stub, it warns `Reflex could not read the type stub
.../party.pyi: Permission denied.` and leaves the file alone, as it does one
you write by hand; make the file readable, or delete it so that the next
compile writes it.

### Errors

The compile stops with these errors:

- `` `nope` is used from my_app.scripts.party, but my_app/scripts/party.js
  exports no function named nope (its functions: celebrate, measure).`` Export
  the function from the file, as in `export function nope() { ... }`, or
  correct the name in Python.
- `` `limit` is used from my_app.scripts.party as a function, but
  my_app/scripts/party.js exports limit as a value, and Python can only call
  functions.`` Export a function that uses the value instead.
- `Syntax error at .../party.js:3:7: Unexpected token.` Fix the code at that
  line and column, in the module or in a file it imports.
- `The JavaScript module my_app.scripts.party imports .../shared.js, which is
  outside .../my_app, the directory of the app's package, and only that
  directory is copied into the compiled app.` Move the file into your app's
  package, or publish it as an npm package and import it by name. A module that
  is a link to a file outside the package gets the same error, with `links to`
  in place of `imports`, and an imported file that is such a link is named with
  its target: `imports .../helper.js, a link to .../shared.js, which is
  outside`.
- `The JavaScript file .../party.js imports .../loop/party.js through
  .../loop, a link back to a directory its imports were already in, so the
  same files are imported again one link deeper, without end.` A link to a
  directory that holds it, such as `loop` pointing to `.`, lets an import reach
  the same file again at a longer path, and each copy of the file would need
  its own. Import the file by a path that does not go through the link, or
  replace the link with a real directory.
- `The JavaScript file .../party.js imports 'fs', a Node.js built-in module,
  which does not exist in the browser.` Remove the import, and do the work that
  needs it in a backend event handler instead.
- `.../.web/script-modules.js printed output that this version of Reflex does
  not read, so it is likely left over from another version.` Delete the `.web`
  directory, and the next run writes it again.

In the browser, a call fails with `Cannot call my_app.scripts.party.nope: the
frontend has no function nope in the JavaScript module my_app.scripts.party.`
when the module does not export a function of that name, which a name used only
in an event handler can reach, or when the frontend was built before the
backend imported it. Export the function, or restart `reflex run` to rebuild
the frontend.

## Using React Hooks

To use React Hooks directly in a Reflex app, you must subclass `rx.Component`,
typically `rx.Fragment` is used when the hook functionality has no visual
element. The hook code is returned by the `add_hooks` method, which is expected
to return a `list[str]` containing Javascript code which will be inserted into the
page component (i.e the render function itself).

For supporting code that must be defined outside of the component render
function, use `_get_custom_code`.

The following example uses `useEffect` to register global hotkeys on the
`document` object, and then triggers an event when a specific key is pressed.

```python demo exec
import dataclasses

from reflex.utils import imports


@dataclasses.dataclass
class KeyEvent:
    """Interface of Javascript KeyboardEvent"""

    key: str = ""


def key_event_spec(ev: rx.Var[KeyEvent]) -> tuple[rx.Var[str]]:
    # Takes the event object and returns the key pressed to send to the state
    return (ev.key,)


class GlobalHotkeyState(rx.State):
    key: str = ""

    @rx.event
    def update_key(self, key):
        self.key = key


class GlobalHotkeyWatcher(rx.Fragment):
    """A component that listens for key events globally."""

    # The event handler that will be called
    on_key_down: rx.EventHandler[key_event_spec]

    def add_imports(self) -> imports.ImportDict:
        """Add the imports for the component."""
        return {
            "react": [imports.ImportVar(tag="useEffect")],
        }

    def add_hooks(self) -> list[str | rx.Var]:
        """Add the hooks for the component."""
        return [
            """
            useEffect(() => {
                const handle_key = %s;
                document.addEventListener("keydown", handle_key, false);
                return () => {
                    document.removeEventListener("keydown", handle_key, false);
                }
            })
            """
            % str(rx.Var.create(self.event_triggers["on_key_down"]))
        ]


def global_key_demo():
    return rx.vstack(
        GlobalHotkeyWatcher.create(
            keys=["a", "s", "d", "w"],
            on_key_down=lambda key: rx.cond(
                rx.Var.create(["a", "s", "d", "w"]).contains(key),
                GlobalHotkeyState.update_key(key),
                rx.console_log(key),
            ),
        ),
        rx.text("Press a, s, d or w to trigger an event"),
        rx.heading(f"Last watched key pressed: {GlobalHotkeyState.key}", as_="h2"),
    )
```

This snippet can also be imported through pip: [reflex-global-hotkey](https://pypi.org/project/reflex-global-hotkey/).
