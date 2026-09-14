# production-app-platform

This example deployment is intended for use with App hosting platforms, like
Azure, AWS, or Google Cloud Run.

## Architecture

The production deployment consists of a few pieces:

- Backend container - built by `Dockerfile` Runs the Reflex backend
  service on port 8000 (or `$PORT`) and is scalable to multiple instances.
  The image contains only the python environment and app source: no bun,
  `node_modules`, or frontend build.
- Redis container - A single instance the standard `redis` docker image should
  share private networking with the backend
- Static frontend - HTML/CSS/JS files that are hosted via a CDN or static file
  server. This is not included in the docker image.

## Deployment

These general steps do not cover the specifics of each platform, but all platforms should
support the concepts described here.

### Vnet

All containers in the deployment should be hooked up to the same virtual private
network so they can access the redis service and optionally the database server.
The vnet should not be exposed to the internet, use an ingress rule to terminate
TLS at the load balancer and forward the traffic to a backend service replica.

### Redis

Deploy a `redis` instance on the vnet.

### Backend

The backend is built by the `Dockerfile` in this directory. When deploying the
backend, be sure to set REFLEX_REDIS_URL=redis://internal-redis-hostname to connect to
the redis service.

With redis available, each replica runs `2 * cpu_count + 1` worker processes.
Set `GRANIAN_WORKERS` to cap this on small instance sizes.

If the app uses postgres, add `psycopg[binary]` to `requirements.txt`; the
binary wheel bundles libpq, so no extra system packages are needed in the image.

### Ingress

Configure the load balancer for the app to forward traffic to port 8000 on the
backend service replicas. Most platforms will generate an ingress hostname
automatically. Make sure when you access the ingress endpoint on `/ping` that it
returns "pong", indicating that the backend is up an available.

The load balancer must support websockets (pass the `Upgrade` header) for the
event connection to work.

### Frontend

The frontend should be hosted on a static file server or CDN.

**Important**: when exporting the frontend, set the `REFLEX_API_URL` environment
variable to the ingress hostname of the backend service.

```bash
REFLEX_API_URL=https://backend.example.com reflex export --frontend-only --no-zip
```

The exported files are in `.web/build/client`. Omit `--no-zip` to get a
`frontend.zip` instead.

If you will host the frontend from a path other than the root, set the
`REFLEX_FRONTEND_PATH` environment variable appropriately when exporting the frontend.

Most static hosts will automatically use the `/404.html` file to handle 404
errors. _This is essential for dynamic routes to work correctly._ Ensure that
missing routes return the `/404.html` content to the user if this is not the
default behavior.

_For Github Pages_: ensure the file `.nojekyll` is present in the root of the repo
to avoid special processing of underscore-prefix directories, like `_next`.

## Platform Notes

The following sections are currently a work in progress and may be incomplete.

### Azure

#### Persistent Storage

If you need to use a database or upload files, you cannot save them to the
container volume. Use Azure Files and mount it into the container at /app/uploaded_files.

#### Resource Types

- Create a new vnet with 10.0.0.0/16
  - Create a new subnet for redis, database, and containers
- Deploy redis as a Container Instances
- Deploy database server as "Azure Database for PostgreSQL"
  - Create a new database for the app
  - Set db-url as a secret containing the db user/password connection string
- Deploy Storage account for uploaded files
  - Enable access from the vnet and container subnet
  - Create a new file share
  - In the environment, create a new files share (get the storage key)
- Deploy the backend as a Container App
  - Create a custom Container App Environment linked up to the same vnet as the redis container.
  - Set REFLEX_REDIS_URL and REFLEX_DB_URL environment variables
  - Add the volume from the environment
  - Add the volume mount to the container
- Deploy the frontend as a Static Web App
