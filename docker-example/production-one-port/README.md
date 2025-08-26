# production-one-port

This docker deployment runs Reflex in prod mode, exposing a single HTTP port:

- `8080` (`$PORT`) - Caddy server hosting the frontend statically and proxying requests to the backend.

The deployment also runs a local Redis server to store state for each user.

Conceptually it is similar to the `simple-one-port` example except it:

- has layer caching for python, reflex, and node dependencies
- uses multi-stage build to reduce the size of the final image

Using this method may be preferable for deploying in memory constrained
environments, because it serves a static frontend export, rather than running
the Vite server via node.

## Build

```console
docker build -t reflex-production-one-port .
```

## Run

```console
docker run -p 8080:8080 reflex-production-one-port
```

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

## Usage

This container should be used with an existing load balancer or reverse proxy to
terminate TLS.

It is also useful for deploying to simple app platforms, such as Render or Heroku.
