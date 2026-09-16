# reflex-sdk

Python client for the [Reflex Cloud](https://build.reflex.dev) API, with synchronous and asynchronous interfaces.

```python
from reflex_sdk import ReflexCloud

with ReflexCloud() as client:
    me = client.auth.me()
    print(me.email, me.tier)
```

```python
from reflex_sdk import AsyncReflexCloud

async with AsyncReflexCloud() as client:
    me = await client.auth.me()
```

## Apps and projects

```python
from reflex_sdk import ReflexCloud

with ReflexCloud() as client:
    projects = client.projects.search("default")
    project = projects[0] if projects else client.projects.create("default")
    app = client.apps.create("dashboard", project_id=project.id)
    client.apps.secrets.set(app.id, {"DATABASE_URL": "postgresql://..."})

    for deployment in client.apps.history(app.id):
        print(deployment.status, deployment.url)

    for record in client.apps.logs(app.id, search="error"):
        print(record.timestamp, record.message)
```

`client.apps` lists, creates, starts, stops, pauses, scales, rolls back and deletes apps, and reads their deployment history and runtime logs; `client.apps.secrets` manages their secrets. `client.projects` lists, searches and creates projects, with `projects.roles` and `projects.members` for access control. `AsyncReflexCloud` has the same methods as coroutines, with `logs` as an async iterator.

## Deploying

```python
from reflex_sdk import DeploymentFailedError, ReflexCloud

with ReflexCloud() as client:
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

## Authentication

The client uses the first access token it finds:

1. The `token` argument.
2. The `REFLEX_ACCESS_TOKEN` environment variable.
3. The token saved on this machine, shared with `reflex login`.

To log in through the browser and save the token for later clients:

```python
import webbrowser

from reflex_sdk import ReflexCloud, credentials

with ReflexCloud() as client:
    login = client.auth.begin_login()
    print(f"Approve the login at {login.url}")
    webbrowser.open(login.url)
    credentials.save_token(client.auth.finish_login(login, timeout=600))
```

`credentials.delete_token()` removes the saved token. Create a token for CI with `client.auth.tokens.create("ci", expires_in_days=30)`.

## Security reviews

```python
review_id = client.security_reviews.submit("source.zip")
result = client.security_reviews.wait(review_id, timeout=600)
for violation in result.violations:
    print(violation.severity, violation.file_path, violation.line, violation.message)
```

Security reviews need the Pro or Enterprise plan. `client.providers` reads whether an organization can deploy to its own Google Cloud, and `client.apps.set_provider`, `set_full_deploy` and `set_instance_bounds` configure where an app runs.

## Errors

Every exception derives from `reflex_sdk.ReflexCloudError`. Error responses raise a subclass of `APIStatusError` matching the status code (`AuthenticationError`, `NotFoundError`, ...), carrying `status_code`, the server's `detail`, and the `request_id` to quote to support. Failed requests are retried up to `max_retries` times when repeating them cannot apply them twice: requests that never reached the server or were turned away with 408 or 429, and `GET`, `HEAD`, `OPTIONS` and `PUT` requests that timed out, lost their connection, or got a 500, 502, 503 or 504 response.

## Transports

`AsyncReflexCloud` sends requests with [aiohttp](https://docs.aiohttp.org) and `ReflexCloud` with [httpx](https://www.python-httpx.org). Pass a transport from `reflex_sdk.transports` to configure the HTTP client, e.g. for proxies, or to use httpx asynchronously:

```python
import aiohttp
import httpx
from reflex_sdk import AsyncReflexCloud, ReflexCloud
from reflex_sdk.transports import AiohttpTransport, AsyncHttpxTransport, HttpxTransport

# Reads HTTP_PROXY, HTTPS_PROXY and NO_PROXY from the environment.
async with aiohttp.ClientSession(trust_env=True) as session:
    async with AsyncReflexCloud(transport=AiohttpTransport(session)) as client:
        ...

client = AsyncReflexCloud(transport=AsyncHttpxTransport())
client = ReflexCloud(transport=HttpxTransport(httpx.Client(proxy="http://proxy:8080")))
```

To use another HTTP library, implement the `Transport` or `AsyncTransport` protocol.

