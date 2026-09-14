# production

This docker deployment runs Reflex in prod mode, exposing a single HTTP port:

- `8080` (`$PORT`) - Caddy server hosting the frontend statically and proxying requests to the backend.

The deployment also runs a local Redis server to store state for each user,
which lets the backend run multiple worker processes.

The frontend is exported at build time and served as static files by Caddy,
so the backend starts in a couple of seconds. The build:

- installs python dependencies in their own layer, so app edits do not
  reinstall them
- keeps bun's package cache between builds, so unchanged frontend
  dependencies are not downloaded again
- uses a multi-stage build so the final image has no bun, `node_modules`, or
  build tooling

## Build

```console
docker build -t reflex-production .
```

To listen on a different port, pass `--build-arg PORT=10000`.

## Run

```console
docker run -p 8080:8080 reflex-production
```

By default the backend runs `2 * cpu_count + 1` workers. Set `GRANIAN_WORKERS`
to a smaller number in memory constrained environments:

```console
docker run -e GRANIAN_WORKERS=2 -p 8080:8080 reflex-production
```

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

## Usage

This container should be used with an existing load balancer or reverse proxy to
terminate TLS.

It is also useful for deploying to simple app platforms, such as Render or Heroku.

If the app defines additional backend API routes, add them to the
`@backend_routes` matcher in the `Caddyfile` so they are forwarded to the backend.
