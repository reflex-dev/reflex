# production-app-platform

This example deployment is intended for use with App hosting platforms, like
Azure, AWS, or Google Cloud Run.

## Architecture

The production deployment consists of a few pieces:
  * Backend container - built by `Dockerfile` Runs the Reflex backend
    service on port 8000 and is scalable to multiple instances.
  * Redis container - A single instance the standard `redis` docker image should
    share private networking with the backend
  * Static frontend - HTML/CSS/JS files that are hosted via a CDN or static file
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
backend, be sure to set REDIS_URL=redis://internal-redis-hostname to connect to
the redis service.

### Ingress

Configure the load balancer for the app to forward traffic to port 8000 on the 
backend service replicas. Most platforms will generate an ingress hostname
automatically. Make sure when you access the ingress endpoint on `/ping` that it
returns "pong", indicating that the backend is up an available.

### Frontend

The frontend should be hosted on a static file server or CDN.

**Important**: when exporting the frontend, set the API_URL environment variable
to the ingress hostname of the backend service.

If you will host the frontend from a path other than the root, set the
`FRONTEND_PATH` environment variable appropriately when exporting the frontend.

Most static hosts will automatically use the `/404.html` file to handle 404
errors. _This is essential for dynamic routes to work correctly._ Ensure that
missing routes return the `/404.html` content to the user if this is not the
default behavior.

_For Github Pages_: ensure the file `.nojekyll` is present in the root of the repo
to avoid special processing of underscore-prefix directories, like `_next`.

## Platform Notes

The following sections are currently a work in progress and may be incomplete.

### Azure

In the Azure load balancer, per-message deflate is not supported. Add the following
to your `rxconfig.py` to workaround this issue.

```python
import uvicorn.workers

import reflex as rx


class NoWSPerMessageDeflate(uvicorn.workers.UvicornH11Worker):
    CONFIG_KWARGS = {
        **uvicorn.workers.UvicornH11Worker.CONFIG_KWARGS,
        "ws_per_message_deflate": False,
    }


config = rx.Config(
    app_name="my_app",
    gunicorn_worker_class="rxconfig.NoWSPerMessageDeflate",
)
```

#### Persistent Storage

If you need to use a database or upload files, you cannot save them to the
container volume. Use Azure Files and mount it into the container at /app/uploaded_files.

#### Resource Types

* Create a new vnet with 10.0.0.0/16
  * Create a new subnet for redis, database, and containers
* Deploy redis as a Container Instances
* Deploy database server as "Azure Database for PostgreSQL"
  * Create a new database for the app
  * Set db-url as a secret containing the db user/password connection string
* Deploy Storage account for uploaded files
  * Enable access from the vnet and container subnet
  * Create a new file share
  * In the environment, create a new files share (get the storage key)
* Deploy the backend as a Container App
  * Create a custom Container App Environment linked up to the same vnet as the redis container.
  * Set REDIS_URL and DB_URL environment variables
  * Add the volume from the environment
  * Add the volume mount to the container
* Deploy the frontend as a Static Web App