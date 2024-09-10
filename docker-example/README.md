# Reflex Docker Examples

This directory contains several examples of how to deploy Reflex apps using docker.

In all cases, ensure that your `requirements.txt` file is up to date and
includes the `reflex` package.

## `simple-two-port`

The most basic production deployment exposes two HTTP ports and relies on an
existing load balancer to forward the traffic appropriately.

## `simple-one-port`

This deployment exports the frontend statically and serves it via a single HTTP
port using Caddy. This is useful for platforms that only support a single port
or where running a node server in the container is undesirable.

## `production-compose`

This deployment is intended for use with a standalone VPS that is only hosting a
single Reflex app. It provides the entire stack in a single `compose.yaml`
including a webserver, one or more backend instances, redis, and a postgres
database.

## `production-app-platform`

This example deployment is intended for use with App hosting platforms, like
Azure, AWS, or Google Cloud Run. It is the backend of the deployment, which
depends on a separately hosted redis instance and static frontend deployment.