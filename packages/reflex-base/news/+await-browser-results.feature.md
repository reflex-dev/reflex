A background event handler can now `await` `rx.call_script`, `rx.call_function` and `rx.run_script` to get the script's result directly, instead of passing a `callback`:

```python
@rx.event(background=True)
async def measure(self):
    size = await rx.call_script("({w: window.innerWidth, h: window.innerHeight})")
    async with self:
        self.width = size["w"]
```

A script error raises `BrowserScriptError`, and a missing result raises `TimeoutError` (`browser_call_timeout` config, or `timeout=` per call). A tab that disconnects and does not reconnect within `browser_call_grace_period` raises `BrowserDisconnectedError`. See [Awaiting Results](https://reflex.dev/docs/api-reference/browser-javascript/#awaiting-results).
