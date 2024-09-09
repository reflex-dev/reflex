# production-compose

This example production deployment uses automatic TLS with Caddy serving static
files for the frontend and proxying requests to both the frontend and backend.
It is intended for use with a standalone VPS that is only hosting a single
Reflex app.

The production app container (`Dockerfile`), builds and exports the frontend
statically (to be served by Caddy). The resulting image only runs the backend
service.

The `webserver` service, based on `Caddy.Dockerfile`, copies the static frontend
and `Caddyfile` into the container to configure the reverse proxy routes that will
forward requests to the backend service. Caddy will automatically provision TLS
for localhost or the domain specified in the environment variable `DOMAIN`.

This type of deployment should use less memory and be more performant since
nodejs is not required at runtime.

## Customize `Caddyfile` (optional)

If the app uses additional backend API routes, those should be added to the
`@backend_routes` path matcher to ensure they are forwarded to the backend.

## Build Reflex Production Service

During build, set `DOMAIN` environment variable to the domain where the app will
be hosted!  (Do not include http or https, it will always use https).

**If `DOMAIN` is not provided, the service will default to `localhost`.**

```bash
DOMAIN=example.com docker compose build
```

This will build both the `app` service from the `prod.Dockerfile` and the `webserver`
service via `Caddy.Dockerfile`.

## Run Reflex Production Service

```bash
DOMAIN=example.com docker compose up
```

The app should be available at the specified domain via HTTPS. Certificate
provisioning will occur automatically and may take a few minutes.

### Data Persistence

Named docker volumes are used to persist the app database (`db-data`),
uploaded_files (`upload-data`), and caddy TLS keys and certificates
(`caddy-data`).

## More Robust Deployment

For a more robust deployment, consider bringing the service up with
`compose.prod.yaml` which includes postgres database and redis cache, allowing
the backend to run with multiple workers and service more requests.

```bash
DOMAIN=example.com docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Postgres uses its own named docker volume for data persistence.

## Admin Tools

When needed, the services in `compose.tools.yaml` can be brought up, providing
graphical database administration (Adminer on http://localhost:8080) and a
redis cache browser (redis-commander on http://localhost:8081). It is not recommended
to deploy these services if they are not in active use.

```bash
DOMAIN=example.com docker compose -f compose.yaml -f compose.prod.yaml -f compose.tools.yaml up -d
```