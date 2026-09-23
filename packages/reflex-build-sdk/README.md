# reflex-build-sdk

Python client for the [Reflex Build](https://build.reflex.dev) API, with synchronous and asynchronous interfaces.

Install it with the HTTP library the client should send requests with:

```bash
pip install "reflex-build-sdk[httpx2]"   # ReflexBuild and AsyncReflexBuild
pip install "reflex-build-sdk[aiohttp]"  # AsyncReflexBuild only
pip install "reflex-build-sdk[httpx]"    # ReflexBuild and AsyncReflexBuild
```

Without any of them, pass the client a [transport](#transports) of your own.

```python
from reflex_build_sdk import ReflexBuild

with ReflexBuild() as client:
    me = client.auth.me()
    print(me.email, me.tier)
```

```python
from reflex_build_sdk import AsyncReflexBuild

async with AsyncReflexBuild() as client:
    me = await client.auth.me()
```

## Apps and projects

```python
from reflex_build_sdk import ReflexBuild

with ReflexBuild() as client:
    projects = client.projects.search("default")
    project = projects[0] if projects else client.projects.create("default")
    app = client.apps.create("dashboard", project_id=project.id)
    client.apps.secrets.set(app.id, {"OPENAI_API_KEY": "sk-..."})

    for deployment in client.apps.history(app.id):
        print(deployment.status, deployment.url)

    for record in client.apps.logs(app.id, search="error"):
        print(record.timestamp, record.message)
```

`client.apps` lists, creates, renames, moves, starts, stops, pauses, scales, rolls back and deletes apps, changes their settings, and reads their status, running deployment, deployment history and runtime logs; `client.apps.secrets` manages their secrets. `client.projects` lists, searches, creates, renames and deletes projects and reads their audit logs, with `projects.roles` (including custom roles), `projects.members` and `projects.teams` for access control. `AsyncReflexBuild` has the same methods as coroutines, with `logs` as an async iterator.

### Custom domains

```python
for record in client.apps.domains.add(app.id, "app.example.com").values():
    print(record.type, record.name, record.value)

domain = client.apps.domains.get(app.id)
print(domain.status, domain.status_detail)
```

`domains.add` returns the DNS records to create, and `domains.get` checks them and reports whether the domain is ready to serve the app. Custom domains need the Pro or Enterprise plan.

## Deploying

```python
from reflex_build_sdk import DeploymentFailedError, ReflexBuild

with ReflexBuild() as client:
    urls = client.apps.reserve_hostname(app.id, app.name)
    # Export the app against urls.frontend_url and urls.backend_url, e.g. with
    # `reflex export`, producing backend.zip and frontend.zip.
    deployment_id = client.deployments.create(
        app.id,
        backend="backend.zip",
        frontend="frontend.zip",
        regions={"sjc": 1},
        on_upload_progress=lambda sent, total: print(f"{sent}/{total} bytes"),
    )
    try:
        report = client.deployments.wait(deployment_id, on_status=print, timeout=900)
    except DeploymentFailedError as error:
        print(error.report.reason, error.report.guidance)
        print(error.report.build_log_excerpt)
        raise
```

`deployments.create` streams the archives straight to storage, then submits the deployment. `deployments.wait` returns the deployment's report once it is running, or awaiting approval (`report.status == "AwaitingApproval"`), and raises `DeploymentFailedError` if it fails. `deployments.status`, `report` and `build_logs` read a deployment's progress, and `regions` and `vm_types` list what can be deployed to.

### Environments

Give an app a pipeline of a dev and a production environment:

```python
pipeline = client.apps.environments.enable(app.id)
production_id = pipeline.production_environment_id
```

An app that has a pipeline already is read rather than enabled again, which fails:

```python
dev, production = client.apps.environments.list(app.id)
production_id = production.id
```

Deployments go to the first environment, and later ones run a version promoted from the one before:

```python
deployment_id = client.deployments.create(
    app.id, backend="backend.zip", frontend="frontend.zip"
)
client.deployments.wait(deployment_id)
promotion = client.apps.environments.promote(app.id, production_id)
client.deployments.wait(promotion.deployment_id)
```

Each environment has its own secrets and URL, and production keeps the app's own id and history. `environments.create`, `update`, `reorder`, `copy_missing_secrets` and `delete` manage the rest of the pipeline. Pipelines need the Enterprise plan.

### Managed database

```python
database = client.apps.database.create(app.id)
print(database.masked_connection_string)
```

`client.apps.database` creates a Postgres database for an app, shared by all of its environments, and sets its connection strings as secrets, `DATABASE_URL` among them, which each environment picks up on its next deployment. Creating or deleting a database needs a token with full access, which `reflex login` tokens are not, and an app with its own `DATABASE_URL` secret is refused.

### Signing users in

```python
client.apps.sign_in.enable(app.id)
client.apps.sign_in.set_audience(app.id, "invited")
client.apps.sign_in.invite(app.id, "someone@example.com")
```

`client.apps.sign_in` lets an app's users sign in with their Reflex accounts, through `rxe.AuthPlugin` from `reflex-enterprise`. It sets the app's sign-in settings as secrets, which take effect when the app is next deployed with `rxe.AuthPlugin`, chooses who may sign in, and lists, exports and blocks the app's users. Restricting who may sign in and inviting addresses need the Pro or Enterprise plan. Changing sign-in needs a token with full access; tokens from `reflex login` are refused.

### Third-party connections

```python
# Inside a deployed app, which is started with its own access token.
with ReflexBuild() as client:
    token = client.apps.connections.credential(app_id, "openai").access_token
    # ... and for one of the app's users:
    token = client.apps.connections.credential(
        app_id, "openai", end_user=user_id
    ).access_token
```

`client.apps.connections` calls third-party services an app is connected to without the app holding their keys: Reflex Build stores the credentials and hands out a live one per call, so read one for each call rather than storing it. `connect_link` starts a connection and returns the page to send someone to, `status` and `list` report what is connected, and `disconnect` ends it. A connection belongs either to the app or to one of its users, named with `end_user`. These need the app's own token, so a client built with no arguments inside a deployed app is already the right one.

## Authentication

The client uses the `token` argument, or the `REFLEX_ACCESS_TOKEN` environment variable when none is passed.

To log in through the browser:

```python
import webbrowser

from reflex_build_sdk import ReflexBuild

with ReflexBuild() as client:
    login = client.auth.begin_login()
    print(f"Approve the login at {login.url}")
    webbrowser.open(login.url)
    token = client.auth.finish_login(login, timeout=600)

with ReflexBuild(token=token) as client:
    print(client.auth.me().email)
```

`client.auth.tokens.revoke_self()` revokes the client's own token, which any token may do. Create a token for CI with `client.auth.tokens.create("ci", expires_in_days=30)`, whose `.token` holds the value, and rotate or revoke one with `client.auth.tokens.refresh(token)`, whose `.token` holds the new value, and `client.auth.tokens.revoke(token)`. If a refresh answers `previous_revoked=False`, the old token is still live and needs revoking. Managing other tokens needs a token with full access, which `reflex login` tokens are not.

`client.usage.balance()` reports how much of the organization's plan allowance is used, and `client.usage.history()` iterates over its charges and credits.

### Pointing at another deployment

The client sends its requests to `https://build.reflex.dev`, or to the `base_url` argument, the `REFLEX_BUILD_BACKEND_URL` environment variable or `REFLEX_CLOUD_BACKEND_URL`, in that order. `begin_login` builds its approval URL the same way, from `ui_url`, `REFLEX_BUILD_URL` or `REFLEX_CLOUD_URL`, and falls back to the client's `base_url`. `reflex-hosting-cli` reads only the `REFLEX_CLOUD_*` names, so set those too for `reflex deploy` to reach the same deployment.

## Security reviews

```python
review_id = client.security_reviews.submit("source.zip")
result = client.security_reviews.wait(review_id, timeout=600)
for violation in result.violations:
    print(violation.severity, violation.file_path, violation.line, violation.message)
```

Security reviews need the Pro or Enterprise plan.

## Google Cloud

Apps can run on an organization's own Google Cloud instead of Reflex Build:

```python
status = client.providers.gcp_status(client.auth.me().org_id)
if status.configured and status.allowed:
    client.apps.set_provider(app.id, "gcp")
    client.apps.set_instance_bounds(app.id, min_instances=1, max_instances=10)
```

Running on Google Cloud needs the Enterprise plan. `client.apps.set_full_deploy` also serves an app's frontend from Google Cloud, and `client.providers.cloud_run_manifest()` returns the Dockerfile and script to deploy to Cloud Run yourself.

Organization admins connect Google Cloud projects with a service account key:

```python
with open("key.json") as key_file:
    client.providers.connect_gcp(
        client.auth.me().org_id,
        service_account_key=key_file.read(),
        project_number="123456789012",
        region="us-central1",
    )
```

`client.providers.gcp_connections` adds, updates, verifies and removes further projects, rotates their keys and chooses the default, and `client.providers.disconnect_gcp` removes them all. These need a token with full access.

## Errors

Every exception derives from `reflex_build_sdk.ReflexBuildError`. Error responses raise a subclass of `APIStatusError` matching the status code (`AuthenticationError`, `NotFoundError`, ...), carrying `status_code`, the server's `detail`, the `code` naming the condition where the API names one (e.g. `"not_connected"`), and the `request_id` to quote to support. Failed requests are retried up to `max_retries` times when repeating them cannot apply them twice: requests that never reached the server or were turned away with 408 or 429, and requests that are harmless to repeat (`GET`, `HEAD`, `OPTIONS` and `PUT` requests, and calls such as `apps.environments.update` that settle on the same result) that timed out, lost their connection, or got a 500, 502, 503 or 504 response.

## Transports

`AsyncReflexBuild` sends requests with the first installed of [aiohttp](https://docs.aiohttp.org), [httpx2](https://github.com/pydantic/httpx2) and [httpx](https://www.python-httpx.org), and `ReflexBuild` with httpx2, or httpx if httpx2 is not installed. Pass a transport from `reflex_build_sdk.transports` to configure the HTTP client, e.g. for proxies, or to pick the HTTP library:

```python
import aiohttp
import httpx2
from reflex_build_sdk import AsyncReflexBuild, ReflexBuild
from reflex_build_sdk.transports import (
    AiohttpTransport,
    AsyncHttpx2Transport,
    Httpx2Transport,
)

# Reads HTTP_PROXY, HTTPS_PROXY and NO_PROXY from the environment.
async with aiohttp.ClientSession(trust_env=True) as session:
    async with AsyncReflexBuild(transport=AiohttpTransport(session)) as client:
        ...

client = AsyncReflexBuild(transport=AsyncHttpx2Transport())
client = ReflexBuild(
    transport=Httpx2Transport(httpx2.Client(proxy="http://proxy:8080"))
)
```

To use another HTTP library, implement the `Transport` or `AsyncTransport` protocol.

