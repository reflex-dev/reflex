Log a warning with the traceback when an ASGI transformer raises before acknowledging lifespan startup, so you can diagnose skipped startup hooks while Reflex continues serving requests.
