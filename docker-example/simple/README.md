# simple

This docker deployment runs Reflex in prod mode with a single process exposing
a single HTTP port:

- `3000` (`$PORT`) - Reflex serves the static frontend and the backend
  (event websocket, `/ping`, `/_upload`).

No reverse proxy or Redis is involved, so the backend runs a single worker
with in-memory state. The app is compiled when the image is built and the
container reuses that compile, but the production frontend bundle is still
rebuilt when the container starts, which adds some time before the app is
reachable.

## Build

```console
docker build -t reflex-simple .
```

## Run

```console
docker run -p 3000:3000 reflex-simple
```

Map the same port on both sides. The frontend connects to the backend using
the hostname it was loaded from and the port the app listens on, so
`-p 8080:3000` will not work over plain HTTP unless `REFLEX_API_URL` is set
to the externally visible address. Behind a TLS-terminating proxy the port is
dropped and the frontend connects to its own origin.

To listen on a different port set `PORT`:

```console
docker run -e PORT=8080 -p 8080:8080 reflex-simple
```

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

## Usage

This container should be used with an existing load balancer or reverse proxy to
terminate TLS. The proxy must pass the `Upgrade` header so the event websocket
can connect.

For example, the following Caddyfile terminates TLS and forwards all traffic
to the container.

```
my-domain.com

reverse_proxy localhost:3000
```
