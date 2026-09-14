# Reflex Docker Examples

This directory contains several examples of how to deploy Reflex apps using docker.

In all cases, ensure that your `requirements.txt` file is up to date and
includes the `reflex` package. Commit the `reflex.lock/` directory that
`reflex init` creates so the frontend dependencies installed in the image match
the ones you developed against.

## `simple-one-process`

The most basic deployment: a single Reflex process serves both the static
frontend and the backend on one port. No reverse proxy, no Redis. The frontend
is rebuilt each time the container starts.

## `production-one-port`

This deployment exports the frontend statically and serves it via a single HTTP
port using Caddy, with a local Redis for state. The backend starts instantly
because the frontend is built into the image, and a multi-stage build keeps
bun, `node_modules`, and other build tooling out of the final image. This is
useful for platforms that only support a single port, such as Render or Heroku.

## `production-compose`

This deployment is intended for use with a standalone VPS that is only hosting a
single Reflex app. It provides the entire stack in a single `compose.yaml`
including a webserver with automatic TLS, one or more backend instances, redis,
and a postgres database.

## `production-app-platform`

This example deployment is intended for use with App hosting platforms, like
Azure, AWS, or Google Cloud Run. It is the backend of the deployment, which
depends on a separately hosted redis instance and static frontend deployment.
