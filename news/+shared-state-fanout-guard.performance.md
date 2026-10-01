Skip the linked-client fan-out on events that changed nothing shared, so an app that defines an `rx.SharedState` no longer resolves the running `App` on every event.
