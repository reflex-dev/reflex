```python exec
import reflex as rx
```

# Self Hosting

Use `reflex deploy` for the managed workflow. Follow this page when you need to run the frontend and backend on your own infrastructure.

Clone your code to a server and install the [requirements](/docs/getting-started/installation/).

## Production Mode

Run your app in production mode:

```bash
reflex run --env prod
```

Production mode compiles the app, builds an optimized static frontend, and
serves it together with the backend (event websocket, `/ping`, `/_upload`)
from a single process on port `3000`. Pass `--frontend-port` or
`--backend-port` to listen on a different port.

The frontend and backend can also run as separate processes, for example to
serve the frontend from a CDN and scale the backend independently:

```bash
reflex run --env prod --backend-only --backend-port 8000
reflex run --env prod --frontend-only --frontend-port 3000
```

```md alert warning
# Reverse Proxy and Websockets
Because the backend uses websockets, some reverse proxy servers, like [nginx](https://nginx.org/en/docs/http/websocket.html) or [apache](https://httpd.apache.org/docs/2.4/mod/mod_proxy.html#protoupgrade), must be configured to pass the `Upgrade` header to allow backend connectivity.
```

## API URL

The frontend connects to the backend at `api_url`. When `api_url` points at
`localhost` (the default), the frontend substitutes the hostname it was loaded
from, and when the page is served over HTTPS it also drops the port and
connects to its own origin. So a single-port production deployment behind a
TLS-terminating proxy needs no `api_url` configuration at all.

Set `api_url` explicitly when the backend is reachable at a different address
than the frontend, for example when the frontend is exported to a static host
and the backend runs elsewhere:

```python
config = rx.Config(
    app_name="your_app_name",
    api_url="https://api.example.com",
)
```

It is also possible to set the environment variable `REFLEX_API_URL` at run
time or export time to retain the default for local development.

## Proxying to a Subpath

If you want to serve the backend behind a reverse proxy at a subpath (e.g.
nginx routing `/api/*` to Reflex), set `backend_path` on the config instead of
baking the prefix into `api_url`. Every backend endpoint (event websocket,
`/ping`, `/_upload`, `/_health`, `/_all_routes`) is mounted under that prefix,
and the frontend baked into the export automatically calls the backend at the
prefixed URLs — no request rewriting in the proxy is required.

```python
config = rx.Config(
    app_name="your_app_name",
    api_url="http://app.example.com:8000",
    backend_path="/api",
)
```

`frontend_path` plays the analogous role for the frontend and the two are
independent.

Note: changing `backend_path` (or `frontend_path`) requires a full restart of
`reflex run` — routes and mount points are registered at startup, so hot
reload alone will not move them.

## Exporting a Static Build

Exporting a static build of the frontend allows the app to be served using a
static hosting provider, such as Netlify or GitHub Pages. Make sure `api_url` is set
to an accessible backend URL when the frontend is exported.

```bash
REFLEX_API_URL=https://api.example.com reflex export
```

This will create a `frontend.zip` file with your app's minified HTML,
Javascript, and CSS build that can be uploaded to your static hosting service.

It also creates a `backend.zip` file with your app's backend Python code to
upload to your server and run.

You can export only the frontend or backend by passing in the `--frontend-only`
or `--backend-only` flags.

It is also possible to export the components without zipping. To do
this, use the `--no-zip` parameter. This provides the frontend in the
`.web/build/client/` directory and the backend can be found in the root directory of
the project.

The export also writes a pre-compressed `.gz` copy of every frontend asset, so
configure the static host to serve those directly where it supports it.

## Reflex Container Service

Another option is to run your Reflex service in a container. Several
`Dockerfile`s with additional documentation are available in the Reflex
project in the directory
[`docker-example`](https://github.com/reflex-dev/reflex/tree/main/docker-example),
ranging from a single process serving everything on one port to a full
compose stack with a TLS-terminating webserver, redis, and postgres.

Before building the image, add a `requirements.txt` to the project folder
that includes `reflex` and commit the `reflex.lock/` directory so the frontend
dependencies installed in the image match the ones you developed against.

The project structure should look like this:

```bash
hello
├── assets
├── hello
│   ├── __init__.py
│   └── hello.py
├── reflex.lock
├── rxconfig.py
├── Dockerfile
└── requirements.txt
```

After all changes have been made, the container image can now be created as follows.

```bash
docker build -t reflex-project:latest .
```

Finally, you can start your Reflex container service as follows.

```bash
docker run -d -p 3000:3000 --name app reflex-project:latest
```
