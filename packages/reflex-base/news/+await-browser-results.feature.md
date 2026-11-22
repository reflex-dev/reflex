A background event handler can now `await` `rx.call_script`, `rx.call_function` and `rx.run_script` outside `async with self` to get the script's result directly, instead of passing a `callback`:

```python
@rx.event(background=True)
async def measure(self):
    size = await rx.call_script("({w: window.innerWidth, h: window.innerHeight})")
    async with self:
        self.width = size["w"]
```

A script error raises `BrowserScriptError`, a missing result `TimeoutError` (`browser_call_timeout` in `rxconfig.py`, or `timeout=` per call), and a tab that is closed, reloaded or away longer than `browser_call_grace_period` raises `BrowserDisconnectedError`. Awaiting inside `async with self` raises `EventHandlerTypeError`. See [Awaiting Results](https://reflex.dev/docs/api-reference/browser-javascript/#awaiting-results).
