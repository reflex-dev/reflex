# Reflex Docker Container

This example describes how to create and use a container image for Reflex with your own code.

## Update Requirements

The `requirements.txt` includes the reflex package which is need to install
Reflex framework. If you use additional packages in your project you have add
this in the `requirements.txt` first. Copy the `Dockerfile`, `.dockerignore` and
the `requirements.txt` file in your project folder.

## Build Reflex Container Image

To build your container image run the following command:

```bash
docker build -t reflex-app:latest . --build-arg API_URL=http://app.example.com:8000
```

Ensure that `API_URL` is set to the publicly accessible hostname or IP where the app
will be hosted.

## Start Container Service

Finally, you can start your Reflex container service as follows:

```bash
docker run -d -p 3000:3000 -p 8000:8000 --name app reflex-app:latest
```

# Production Service with Docker Compose and Caddy

An example production deployment uses automatic TLS with Caddy serving static files
for the frontend and proxying requests to both the frontend and backend.

Copy `compose.yaml`, `Caddy.Dockerfile` and `Caddyfile` to your project directory. The production
build leverages the same `Dockerfile` described above.

## Customize `Caddyfile`

If the app uses additional backend API routes, those should be added to the
`@backend_routes` path matcher to ensure they are forwarded to the backend.

## Build Reflex Production Service

During build, set `DOMAIN` environment variable to the domain where the app will
be hosted!  (Do not include http or https, it will always use https)

```bash
DOMAIN=example.com docker compose build
```

This will build both the `app` service from the existing `Dockerfile` and the `webserver`
service via `Caddy.Dockerfile` that copies the `Caddyfile` and static frontend export
from the `app` service into the container.

## Run Reflex Production Service

```bash
DOMAIN=example.com docker compose up -d
```

The app should be available at the specified domain via HTTPS. Certificate
provisioning will occur automatically and may take a few minutes.