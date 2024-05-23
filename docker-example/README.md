# Reflex Docker Container

This example describes how to create and use a container image for Reflex with your own code.

## Update Requirements

The `requirements.txt` includes the reflex package which is needed to install
Reflex framework. If you use additional packages in your project you have to add
this in the `requirements.txt` first. Copy the `Dockerfile`, `.dockerignore` and
the `requirements.txt` file in your project folder.

## Build Simple Reflex Container Image

The main `Dockerfile` is intended to build a very simple, single container deployment that runs
the Reflex frontend and backend together, exposing ports 3000 and 8000.

To build your container image run the following command:

```bash
docker build -t reflex-app:latest .
```

## Start Container Service

Finally, you can start your Reflex container service as follows:

```bash
docker run -it --rm -p 3000:3000 -p 8000:8000 --name app reflex-app:latest
```

It may take a few seconds for the service to become available.

Access your app at http://localhost:3000.

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

# Production Service with Docker Compose and Caddy

An example production deployment uses automatic TLS with Caddy serving static files
for the frontend and proxying requests to both the frontend and backend.

Copy the following files to your project directory:
  * `compose.yaml`
  * `compose.prod.yaml`
  * `compose.tools.yaml`
  * `prod.Dockerfile`
  * `Caddy.Dockerfile`
  * `Caddyfile`

The production app container, based on `prod.Dockerfile`, builds and exports the
frontend statically (to be served by Caddy). The resulting image only runs the
backend service.

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

# Container Hosting

Most container hosting services automatically terminate TLS and expect the app
to be listening on a single port (typically `$PORT`).

To host a Reflex app on one of these platforms, like Google Cloud Run, Render,
Railway, etc, use `app.Dockerfile` to build a single image containing a reverse
proxy that will serve that frontend as static files and proxy requests to the
backend for specific endpoints.

If the chosen platform does not support buildx and thus heredoc, you can copy
the Caddyfile configuration into a separate Caddyfile in the root of the
project.
