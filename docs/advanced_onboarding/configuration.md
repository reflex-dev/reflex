
# Configuration

Reflex apps can be configured using a configuration file, environment variables, and command line arguments.

## Configuration File

Running `uv run reflex init` will create an `rxconfig.py` file in your root directory.
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

See the [config reference](/docs/api-reference/config/) for all the parameters available.

## Environment Variables

Any config parameter can be overridden by setting an environment variable with the `REFLEX_` prefix and the parameter name in uppercase. Environment variables take precedence over values set in `rxconfig.py`.

For example, to override the `frontend_port` setting:

```bash
REFLEX_FRONTEND_PORT=3001 uv run reflex run
```

The [config reference](/docs/api-reference/config/) lists the environment variable corresponding to each config parameter. Reflex also honors additional environment variables that are not config parameters — see [environment variables](/docs/api-reference/environment-variables/) for those.

## Command Line Arguments

Finally, you can override the configuration file and environment variables by passing command line arguments to `uv run reflex run`.

```bash
uv run reflex run --frontend-port 3001
```

See the [CLI reference](/docs/api-reference/cli) for all the arguments available.

## Loading a .env File

Set `env_file` (or the `REFLEX_ENV_FILE` environment variable) to load environment variables from a dotenv-format file before the config is read. This requires the `python-dotenv` package to be installed.

```python
config = rx.Config(
    app_name="my_app_name",
    env_file=".env",
)
```

Multiple files can be passed separated by `os.pathsep` (`:` on Linux/macOS, `;` on Windows); when several files set the same variable, the first file in the list takes precedence. Values from an env file override variables already present in the environment.

Because the env file is loaded before config overrides are applied, it can set any `REFLEX_*` variable, e.g. `REFLEX_FRONTEND_PORT=3001`.

## The App Module

`app_name` tells Reflex where your app lives: by default it imports the module `<app_name>.<app_name>` (the layout created by `reflex init`) and expects it to define a module-level variable named `app`, an instance of `rx.App`.

Set `app_module_import` to load the app from a different module, e.g. a `src` layout or a package entry point:

```python
config = rx.Config(
    app_name="my_app_name",
    # Equivalent to `from mypkg.main import app`.
    app_module_import="mypkg.main",
)
```

The imported module must still define `app` at module level.

## Ports, Hosts and URLs

- `frontend_port` (default `3000`) and `backend_port` (default `8000`) control which ports the frontend and backend listen on. In dev mode, if a port is taken, the next available port is used.
- `backend_host` (default `0.0.0.0`) is the address the backend server binds to.
- `api_url` (default `http://localhost:8000`) is the URL the user's **browser** uses to reach the backend. You typically don't need to set it: when `api_url` points at localhost, the frontend substitutes the domain the app was served from, so a backend reachable at the same address as the frontend (e.g. behind a reverse proxy or load balancer) is found automatically. Set `api_url` only when the backend is listening on a different address than the frontend, e.g. `https://api.example.com`.
- `deploy_url` (default `http://localhost:3000`) is the public URL where the **frontend** is hosted. Reflex uses it wherever an absolute frontend URL is needed — most notably for the links in the generated `sitemap.xml`. It is also the origin browsers will present when connecting to the backend, which matters for CORS (below).

## CORS

The backend only accepts cross-origin requests from origins listed in `cors_allowed_origins`. The default, `["*"]`, allows any origin — convenient in development, but in production restrict it to the origins your frontend is actually served from (typically the origin of `deploy_url`):

```python
config = rx.Config(
    app_name="my_app_name",
    api_url="https://api.example.com",
    deploy_url="https://example.com",
    cors_allowed_origins=["https://example.com"],
)
```

The setting applies to both regular HTTP endpoints and the WebSocket connection. As an environment variable, pass a comma-separated list:

```bash
REFLEX_CORS_ALLOWED_ORIGINS="https://example.com,https://www.example.com" uv run reflex run
```

## Path Prefixes

By default the frontend is served from the root of its domain and backend routes are mounted at the root of the backend server. Two settings change that, e.g. when the app shares a domain with other services behind a reverse proxy:

- `frontend_path` serves the frontend under a sub-path: `frontend_path="/app"` serves the frontend at `http://localhost:3000/app`.
- `backend_path` mounts all backend routes under a prefix: `backend_path="/api"` mounts the event WebSocket and the `/ping`, `/_upload`, `/_health`, and `/_all_routes` endpoints under `/api`. The prefix is automatically included in the backend URLs baked into the frontend. Routes are registered at startup, so changing it requires a full `reflex run` restart.

Both values are normalized to start with a `/`.

## Plugins

Plugins extend the Reflex compiler. Add plugin instances via the `plugins` parameter, and disable plugins that are enabled by default (like the sitemap plugin) with `disable_plugins`:

```python
config = rx.Config(
    app_name="my_app_name",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
    # Or turn off a default-enabled plugin:
    # disable_plugins=[rx.plugins.SitemapPlugin],
)
```

Plugins can also be specified in the environment as fully qualified import paths, separated by `:`. Plugins specified this way are instantiated without arguments, so plugins that require constructor arguments must be configured in `rxconfig.py`.

- `REFLEX_PLUGINS` **replaces** the `plugins` list from `rxconfig.py`.
- `REFLEX_EXTRA_PLUGINS` **appends** to the configured plugins, skipping any that are already configured or disabled.
- `REFLEX_DISABLE_PLUGINS` lists plugin classes to disable.

```bash
REFLEX_EXTRA_PLUGINS="reflex.plugins.SitemapPlugin" uv run reflex run
```

See the [plugins reference](/docs/api-reference/plugins/) for the available plugins and how to write your own.

## Customizable App Data Directory

The `REFLEX_DIR` environment variable can be set, which allows users to set the location where Reflex writes helper tools like Bun and NodeJS.

By default we use Platform specific directories:

On windows, `C:/Users/<username>/AppData/Local/reflex` is used.

On macOS, `~/Library/Application Support/reflex` is used.

On linux, `~/.local/share/reflex` is used.
