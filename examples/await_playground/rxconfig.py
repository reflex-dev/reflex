import reflex as rx

config = rx.Config(
    app_name="await_playground",
    # Default per-call wait before TimeoutError; a call's timeout= overrides it.
    browser_call_timeout=30.0,
    # Short so the Disconnect page's experiments finish quickly (default 5s).
    browser_call_grace_period=3.0,
)
