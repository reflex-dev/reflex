```python exec
import reflex as rx
```

# Self Hosting

Use `reflex deploy` for the managed workflow. Follow this page when you need to run the frontend and backend on your own infrastructure.

Clone your code to a server and install the [requirements](/docs/getting-started/installation/).

## API URL

Edit your `rxconfig.py` file and set `api_url` to the publicly accessible IP
address or hostname of your server, with the port `:8000` at the end. Setting
this correctly is essential for the frontend to interact with the backend state.

For example, if your server is at `app.example.com`, use:

```python
config = rx.Config(
    app_name="your_app_name",
    api_url="http://app.example.com:8000",
)
```

It is also possible to set the environment variable `API_URL` at run time or
export time to retain the default for local development.

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

## Production Mode

Then run your app in production mode:

```bash
reflex run --env prod
```

Production mode creates an optimized build of your app.  By default, the static
frontend of the app (HTML, Javascript, CSS) will be exposed on port `3000` and
the backend (event handlers) will be listening on port `8000`.

```md alert warning
# Reverse Proxy and Websockets
Because the backend uses websockets, some reverse proxy servers, like [nginx](https://nginx.org/en/docs/http/websocket.html) or [apache](https://httpd.apache.org/docs/2.4/mod/mod_proxy.html#protoupgrade), must be configured to pass the `Upgrade` header to allow backend connectivity.
```

## Exporting a Static Build

Exporting a static build of the frontend allows the app to be served using a
static hosting provider, such as Netlify or GitHub Pages. Make sure `api_url` is set
to an accessible backend URL when the frontend is exported.

```bash
API_URL=http://app.example.com:8000 reflex export
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

## Reflex Container Service

Another option is to run your Reflex service in a container. For this
purpose, a `Dockerfile` and additional documentation is available in the Reflex
project in the directory `docker-example`.

Before building the image, update `rxconfig.py` and add `requirements.txt` to
the project folder:

```python
config = rx.Config(
    app_name="app",
    api_url="http://app.example.com:8000",
)
```

Notice that the `api_url` should be set to the externally accessible hostname or
IP, as the client browser must be able to connect to it directly to establish
interactivity.

You can find the `requirements.txt` in the `docker-example` folder of the
project too.

The project structure should look like this:

```bash
hello
├── .web
├── assets
├── hello
│   ├── __init__.py
│   └── hello.py
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
docker run -d -p 3000:3000 -p 8000:8000 --name app reflex-project:latest
```
