# Await playground

A Reflex app to play with awaiting browser scripts from background event handlers
(reflex-dev/reflex PR #7955, branch `farhan/focused-darwin-dx76ek-await-results`):

```python
@rx.event(background=True)
async def measure(self):
    size = await rx.call_script("({w: innerWidth, h: innerHeight})")
    async with self:
        self.viewport = f"{size['w']} x {size['h']}"
```

## Run

The feature is in `reflex-base` as well as `reflex`, so run the app with the
environment of the checkout this directory sits in:

```sh
(cd ../.. && uv sync)
uv run --project ../.. reflex run
```

Open http://localhost:3000. Every page appends to its own log, with seconds since the
handler started. Keep the terminal visible: the Errors page's "Uncaught" button raises
on the backend.

## Pages

| Route | Shows |
|---|---|
| `/` Basics | `await rx.call_script` returning dict/list/None, promises, chaining results, `call_function` and `run_script`, scripts with Vars, latency, progress from a loop |
| `/dialogs` Ask the user | `confirm()` before delete, `prompt()`, a multi-step wizard driven by an in-page question card, all with `timeout=None`; the tab stays responsive meanwhile |
| `/errors` Errors | `BrowserScriptError` (throw, reject, non-Error), `BrowserResultSerializationError` (DOM node, window, function, symbol, 2 MB, deep nesting, circular), per-call `timeout=`, late results dropped, invalid timeouts, `callback=` plus await, await under the state lock, an uncaught error |
| `/concurrent` Concurrency | five handlers awaiting at once, `asyncio.gather`, a race with cancellation, an 8 s await while a regular handler keeps counting clicks |
| `/disconnect` Disconnects | a socket drop under and over `browser_call_grace_period` (3 s here), a call made while dropped, reload/close during an open await |

Settings live in `rxconfig.py`: `browser_call_timeout` (default 30 s) and
`browser_call_grace_period` (default 5 s, set to 3 s here). Both also take
`REFLEX_BROWSER_CALL_TIMEOUT` / `REFLEX_BROWSER_CALL_GRACE_PERIOD`.
