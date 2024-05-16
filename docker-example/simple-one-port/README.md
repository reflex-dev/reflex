# simple-one-port

This docker deployment runs Reflex in prod mode, exposing a single HTTP port:
  * `8080` (`$PORT`) - Caddy server hosting the frontend statically and proxying requests to the backend.

The deployment also runs a local Redis server to store state for each user.

Using this method may be preferable for deploying in memory constrained
environments, because it serves a static frontend export, rather than running
the NextJS server via node.

For platforms which only terminate TLS to a single port, this container can be
deployed instead of the `simple-two-port` example.

## Build

```console
docker build -t reflex-simple-one-port .
```

## Run

```console
docker run -p 8080:8080 reflex-simple-one-port
```

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

## Usage

This container should be used with an existing load balancer or reverse proxy to
terminate TLS.

It is also useful for deploying to simple app platforms, such as Render or Heroku.