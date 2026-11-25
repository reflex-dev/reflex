`rx.window_event_listener` registers its handler again whenever the handler changes, so a handler that reads state or client state no longer keeps the values from the first render.
