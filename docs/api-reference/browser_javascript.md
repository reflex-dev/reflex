```python exec
import asyncio
from typing import Any
import reflex as rx
from pcweb.pages.docs import wrapping_react
from pcweb.pages.docs import library
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

- `rx.script` - Injects the script via `next/script` for efficient loading of inline and external Javascript code. Described further in the [component library]({library.other.script.path}).
  - These components can be directly included in the body of a page, or they may
    be passed to `rx.App(head_components=[rx.script(...)])` to be included in
    the `<Head>` tag of all pages.
- `rx.call_script` - An event handler that evaluates arbitrary Javascript code,
  and optionally returns the result to another event handler.

These previous two methods can work in tandem to load external scripts and then
call functions defined within them in response to user events.

The following two methods are geared towards wrapping components and are
described with examples in the [Wrapping React]({wrapping_react.overview.path})
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
        rx.script("""
            var button_sfx = new Audio("/vintage-button-sound-effect.mp3")
            function playFromStart (sfx) {sfx.load(); sfx.play()}"""),
        rx.button("Play Immediately", on_click=rx.call_script("playFromStart(button_sfx)")),
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
            rx.call_script(
                "window.location",
                callback=WindowState.update_location
            ),
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
                rx.console_log(key)
            )
        ),
        rx.text("Press a, s, d or w to trigger an event"),
        rx.heading(f"Last watched key pressed: {GlobalHotkeyState.key}"),
    )
```

This snippet can also be imported through pip: [reflex-global-hotkey](https://pypi.org/project/reflex-global-hotkey/).
