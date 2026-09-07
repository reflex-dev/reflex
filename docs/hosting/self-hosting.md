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

## Reusing a Production Frontend Build

For repeated deployments with deterministic frontend builds, you can opt in to a
local build cache:

```bash
REFLEX_FRONTEND_BUILD_CACHE=true reflex deploy
```

The same option works with `reflex export` and production-mode `reflex run`.
It is disabled by default. On a cache hit, Reflex restores the pristine JavaScript
build, then runs post-build plugins, fallback generation, compression, and frontend
path processing again. Python compilation and the normal dependency checks still run.

On macOS and Linux, production exports sharing `.web` wait for one another from
compilation through ZIP creation. Production and preview startup also hold this
lock while compiling and building, even when caching is disabled. The lock file
`.web/.reflex-build.lock` remains in place between commands; do not remove it while
a command is running. Initialization, development hot reload, and unrelated tools
writing to `.web` are outside this lock, so avoid running them during an export.

Enable this option only when build output is determined by the tracked local inputs.
Prerendering, Vite plugins, and custom export scripts can read remote data, the clock,
or files outside `.web`; changes to those inputs require a fresh build. Run with
`REFLEX_FRONTEND_BUILD_CACHE=false` to force one and discard the previous snapshot,
or remove `.web/reflex.build-cache`. Re-enabling the option then populates a new cache.

The cache checks generated frontend source, assets and configuration within `.web`,
the build environment, runtime identity, and installed dependency file metadata.
It also verifies snapshot file contents before restoring them. Use it on a local
macOS or Linux filesystem that reports file modification and change timestamps
reliably; the cache is bypassed on Windows and when links lead outside tracked inputs.

Production exports and production/preview frontend builds sharing the same `.web`
directory wait for an exclusive workspace lock on macOS, Linux, and Windows,
including when caching is disabled. The lock covers compilation through build and
archive creation, and is released before a server starts serving. Initialization,
development hot reload, and unrelated workspace writers do not participate.

Generated build output, `.react-router`, the build lock, the dependency-install cache marker, and
the top-level `node_modules/.vite`, `.vite-temp`, and `.cache` directories are
excluded from the input fingerprint. The private `last_reflex_run_datetime`,
`last_version_check_datetime`, and `last_version_check_attempt_datetime` fields in
`reflex.json`, including their per-package timestamp variants, are also excluded. Custom code
that uses these excluded values or files to determine build output should keep the
cache disabled. Cache hits can retain the earlier private timestamps embedded in
bundles; the client framework uses the separately checked Reflex version value.

Cache misses perform a normal build and have extra fingerprinting and snapshot-copy
work, so this option is most useful when the same frontend is deployed repeatedly.
Deleting `.web` also deletes its cached build.

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
