# production-compose

This example production deployment uses automatic TLS with Caddy serving static
files for the frontend and proxying requests to the backend.
It is intended for use with a standalone VPS that is only hosting a single
Reflex app.

The production app container (`Dockerfile`), builds and exports the frontend
statically (to be served by Caddy). The resulting image only runs the backend
service and contains no bun, `node_modules`, or build tooling.

The `webserver` service, based on `Caddy.Dockerfile`, copies the static frontend
out of the app image and `Caddyfile` into the container to configure the
reverse proxy routes that will forward requests to the backend service. Caddy
will automatically provision TLS for localhost or the domain specified in the
environment variable `DOMAIN`.

This type of deployment should use less memory and be more performant since
neither bun nor nodejs is required at runtime.

## Customize `Caddyfile` (optional)

If the app uses additional backend API routes, those should be added to the
`@backend_routes` path matcher to ensure they are forwarded to the backend.

## Build Reflex Production Service

During build, set `DOMAIN` environment variable to the domain where the app will
be hosted! (Do not include http or https, it will always use https).

**If `DOMAIN` is not provided, the service will default to `localhost`.**

```bash
DOMAIN=example.com docker compose build
```

This will build both the `app` service from the `Dockerfile` and the `webserver`
service via `Caddy.Dockerfile`. The `webserver` build copies the exported
frontend out of the `app` image, so compose always builds `app` first.

## Run Reflex Production Service

```bash
DOMAIN=example.com docker compose up
```

The app should be available at the specified domain via HTTPS. Certificate
provisioning will occur automatically and may take a few minutes.

### Data Persistence

Named docker volumes are used to persist the app database (`db-data`),
uploaded_files (`upload-data`), and caddy TLS keys and certificates
(`caddy-data`). Keep `caddy-data` across container recreations so certificates
are not re-issued each time, which can hit Let's Encrypt rate limits.

## More Robust Deployment

For a more robust deployment, consider bringing the service up with
`compose.prod.yaml` which includes postgres database and redis cache, allowing
the backend to run with multiple workers and service more requests.

```bash
DOMAIN=example.com docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Add `psycopg[binary]` to `requirements.txt` so the backend can connect to
postgres; the binary wheel bundles libpq, so no extra system packages are
needed in the image.

With redis available, the backend runs `2 * cpu_count + 1` worker processes.
Set `GRANIAN_WORKERS` in the `app` environment to cap this on memory
constrained hosts.

Postgres uses its own named docker volume for data persistence.

## Admin Tools

When needed, the services in `compose.tools.yaml` can be brought up, providing
graphical database administration (Adminer on http://localhost:8080) and a
redis cache browser (redis-commander on http://localhost:8081). It is not recommended
to deploy these services if they are not in active use.

```bash
DOMAIN=example.com docker compose -f compose.yaml -f compose.prod.yaml -f compose.tools.yaml up -d
```
