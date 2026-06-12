```python exec
import reflex as rx
```

# Frontend Inspector

The frontend inspector maps rendered DOM nodes back to the Python source line that created them. Hover an element in the browser, see which `Component.create(...)` call produced it, and click to open that line in your editor.

It is a development-only tool. The plugin is a no-op under `REFLEX_ENV_MODE=prod`, so the same `rxconfig.py` works for both dev and prod runs.

## Enable

Add `FrontendInspectorPlugin` to `plugins` in your `rxconfig.py`:

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    plugins=[rx.plugins.FrontendInspectorPlugin()],
)
```

Run your app in dev mode (`uv run reflex run`). The inspector loads automatically; the `launch-editor` dev dependency is installed during the same compile pass.

## Usage

Three modes:

- **Hover with `alt` held** — show the overlay while inspecting. The overlay disappears as soon as you release `alt`.
- **`alt+x`** — toggle persistent mode. The overlay stays on; the small `rx-inspect` button in the bottom-right corner reflects the state.
- **`alt`+click** — open the source file at the captured line in your editor. The modifier is required at click time so re-focusing the browser window doesn't hijack normal clicks.

`Esc` exits persistent mode. Pressing `c` while hovering copies `path:line:column` to the clipboard.

## Configuration

```python
config = rx.Config(
    app_name="my_app",
    plugins=[
        rx.plugins.FrontendInspectorPlugin(
            # Custom shortcut. Modifier aliases like cmd / option are accepted.
            shortcut="ctrl+shift+i",
            # Optional: override the editor invocation. Empty falls back to
            # $REFLEX_EDITOR / $VISUAL / $EDITOR / launch-editor's auto-detection.
            editor="code -g",
        ),
    ],
)
```

| Argument | Default | Notes |
| --- | --- | --- |
| `shortcut` | `"alt+x"` | Modifiers: `alt`, `ctrl`, `meta` (`cmd`/`super`/`win`), `shift`. |
| `editor` | `""` | Forwarded to [`launch-editor`](https://github.com/yyx990803/launch-editor). |

## Production safety

The plugin's hooks all return empty when `REFLEX_ENV_MODE=prod`, so prod builds emit no inspector wiring:

- `uv run reflex run --env prod`
- `uv run reflex export --env prod`
- Any deploy that sets `REFLEX_ENV_MODE=prod`.

The gate is re-evaluated at every emission site, so the same `rxconfig.py` works in both dev and prod without further changes.

## What it does and does not do

It does:

- Add a small `data-rx="<id>"` attribute to every component that has a non-Fragment tag.
- Emit `.web/public/__reflex/source-map.json` mapping ids to `(file, line, column, component)`.
- Mount a Vite dev-server middleware at `/__open-in-editor` that calls `launch-editor`.

It does not:

- Inspect React state or props at runtime — it is a source-mapping tool, not a React DevTools replacement.
- Run in production. The Vite plugin is registered with `apply: 'serve'`, so even if a stray asset slipped through, prod builds would not load it.
- Modify your source code. The inspector stores a private id on each component that gets rendered out as a `data-rx` attribute; your `rxconfig.py` and component files are untouched.

## Programmatic toggle

When the inspector is loaded, `window.__REFLEX_INSPECTOR__` exposes the runtime API for ad-hoc debugging in the browser console:

```js
window.__REFLEX_INSPECTOR__.enable();
window.__REFLEX_INSPECTOR__.toggle();
window.__REFLEX_INSPECTOR__.sourceCount(); // number of mapped ids
```
