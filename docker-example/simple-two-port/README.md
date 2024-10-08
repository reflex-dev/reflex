# simple-two-port

This docker deployment runs Reflex in prod mode, exposing two HTTP ports:
  * `3000` - node NextJS server using optimized production build
  * `8000` - python gunicorn server hosting the Reflex backend

The deployment also runs a local Redis server to store state for each user.

## Build

```console
docker build -t reflex-simple-two-port .
```

## Run

```console
docker run -p 3000:3000 -p 8000:8000 reflex-simple-two-port
```

Note that this container has _no persistence_ and will lose all data when
stopped. You can use bind mounts or named volumes to persist the database and
uploaded_files directories as needed.

## Usage

This container should be used with an existing load balancer or reverse proxy to
route traffic to the appropriate port inside the container.

For example, the following Caddyfile can be used to terminate TLS and forward
traffic to the frontend and backend from outside the container.

```
my-domain.com

encode gzip

@backend_routes path /_event/* /ping /_upload /_upload/*
handle @backend_routes {
	reverse_proxy localhost:8000
}

reverse_proxy localhost:3000
```