Overriding `EventNamespace.on_event` is deprecated: override `handle_event`, which runs for every event, including the hydrate on connect, on both transports. Replace `reflex.app.WebsocketEventNamespace` the same way to cover the default transport; see [Running code for every event](https://reflex.dev/docs/changelog/upgrading/upgrading-to-0-10/#running-code-for-every-event).

```python
# Before
class AuditingNamespace(EventNamespace):
    async def on_event(self, sid, data):
        audit(sid, data)
        await super().on_event(sid, data)


# After
class AuditingNamespace(EventNamespace):
    async def handle_event(self, sid, data, asgi_scope):
        audit(sid, data)
        await super().handle_event(sid, data, asgi_scope)
```
