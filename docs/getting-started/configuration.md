```python exec
config_api_ref_url = "/docs/api-reference/config"
cli_api_ref_url = "/docs/api-reference/cli"
```

# Configuration

Reflex apps can be configured using a configuration file, environment variables, and command line arguments.

## Configuration File

Running `reflex init` will create an `rxconfig.py` file in your root directory.
You can pass keyword arguments to the `Config` class to configure your app.

For example:

```python
# rxconfig.py
import reflex as rx

config = rx.Config(
    app_name="my_app_name",
    # Connect to your own database.
    db_url="postgresql://user:password@localhost:5432/my_db",
    # Change the frontend port.
    frontend_port=3001,
)
```

See the [config reference]({config_api_ref_url}) for all the parameters available.

## Environment Variables

You can override the configuration file by setting environment variables.
For example, to override the `frontend_port` setting, you can set the `FRONTEND_PORT` environment variable.

```bash
FRONTEND_PORT=3001 reflex run
```

## Command Line Arguments

Finally, you can override the configuration file and environment variables by passing command line arguments to `reflex run`.

```bash
reflex run --frontend-port 3001
```

See the [CLI reference]({cli_api_ref_url}) for all the arguments available.

## Anonymous Usage Statistics

Reflex collects completely anonymous telemetry data about general usage.
Participation in this anonymous program is optional, and you may opt-out if you'd not like to share any information.

### What's Being Collected

Telemetry allows us to understand how Reflex is used, what features are most important, and how we can improve the product.

The following information is collected:

* Operating system
* CPU count
* Memoryd
* Python version
* Reflex version

### How to Opt-Out

To disable telemetry, set `telemetry_enabled=False` in your `rxconfig.py` file.

```python
config = rx.Config(
    app_name="hello",
    telemetry_enabled=False,
)
```

Alternatively, you can set the `TELEMETRY_ENABLED` environment variable to `False`.

## Customizable App Data Directory

The `REFLEX_DIR` environment variable can be set, which allows users to set the location where Reflex writes helper tools like Bun and NodeJS.

By default we use Platform specific directories:

On windows, `C:/Users/<username>/AppData/Local/reflex` is used.

On macOS, `~/Library/Application Support/reflex` is used.

On linux, `~/.local/share/reflex` is used.
