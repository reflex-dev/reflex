# Telemetry

Reflex collects anonymized usage statistics — counts of components and built-in features used at compile time, along with versions of Reflex, Python, and the host OS — so we can prioritize bug fixes and guide the future direction of the framework. We do **not** collect the contents of your source files, state, or any data your app handles at runtime.

For full details, see our [Privacy Policy](https://build.reflex.dev/privacy-policy) and [Terms of Service](https://build.reflex.dev/terms-of-use).

If you log in to [Reflex Cloud](/docs/hosting/deploy-quick-start/), your Cloud account identifier is associated with subsequent usage events from that machine.

## Opt out

In your `rxconfig.py`:

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    telemetry_enabled=False,
)
```

Or via environment variable:

```bash
REFLEX_TELEMETRY_ENABLED=0 reflex init --template blank
```

The environment variable is the only supported opt-out method for reflex
commands executed outside the context of an app directory, such as `reflex
login` and `reflex init`.
