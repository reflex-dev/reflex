

<!-- towncrier release notes start -->

## v0.0.5 (2026-09-24)

### Features

- Response models carry the fields the API returns that they previously dropped: `App` gains `backend_url`, `disable_secrets`, `weekly_report_enabled`, `source_thread_id`, `unreleased_provider` and the `any_environment_*` flags; `AppDeployment` gains `strategy`, `persistent` and `screenshot_uri`; `DeploymentRecord` gains `updated_by` and `promoted_from_id`; `ProjectAppDeployment` gains `updated_at`, `updated_by` and the `vm_type_*` fields; `Project` gains the `org_*` usage fields; `ProjectApp` gains `from_builder`; `ProjectMember` gains `role_permissions`; `AppSummary` gains `disable_secrets`; and `LogRecord` gains `event_id`, `stream_id` and `revision_id`. ([#7311](https://github.com/reflex-dev/reflex/issues/7311))


## v0.0.4 (2026-09-23)

### Breaking Changes

- The HTTP libraries are optional extras, so installing `reflex-build-sdk` alone no longer pulls in aiohttp or httpx. Install the one the client should use:

  ```bash
  pip install "reflex-build-sdk[httpx2]"  # or [aiohttp], [httpx]
  ```

  Or pass the client a transport of your own. ([#7290](https://github.com/reflex-dev/reflex/issues/7290))
- The clients no longer read the token saved by `reflex login`, and the `reflex_build_sdk.credentials` module is removed. Pass `token=` or set `REFLEX_ACCESS_TOKEN`. ([#7290](https://github.com/reflex-dev/reflex/issues/7290))

### Features

- Add `Httpx2Transport` and `AsyncHttpx2Transport`, sending requests with [httpx2](https://github.com/pydantic/httpx2). Both clients use httpx2 by default over httpx, and `AsyncReflexBuild` still prefers aiohttp. ([#7290](https://github.com/reflex-dev/reflex/issues/7290))


## v0.0.3 (2026-09-23)

### Breaking Changes

- `auth.tokens.create` returns a `CreatedToken` and `auth.tokens.refresh` a `RotatedToken`, rather than the bare token value. Read the value from `.token`:

  ```python
  token = client.auth.tokens.create("ci").token
  ```

  If a refresh returns `previous_revoked=False`, the old token is still live; revoke it with `auth.tokens.revoke`. ([#7277](https://github.com/reflex-dev/reflex/issues/7277))

### Features

- Add `auth.tokens.revoke_self()`, which revokes the client's own token and works with any token, and `Me.app_id`, the app an app token was provisioned for. ([#7277](https://github.com/reflex-dev/reflex/issues/7277))

### Bug Fixes

- `deployments.wait` raises the API's `UnprocessableEntityError` for a malformed deployment id, rather than `ValueError`. ([#7240](https://github.com/reflex-dev/reflex/issues/7240))
- `auth.tokens.refresh`, `apps.create` and `projects.list` call the routes Reflex Build serves, and `apps.history` decodes deployments without a URL. ([#7277](https://github.com/reflex-dev/reflex/issues/7277))


## v0.0.2 (2026-09-18)

### Breaking Changes

- The clients are now named `ReflexBuild` and `AsyncReflexBuild`, and the base exception `ReflexBuildError`, matching the Reflex Build product they talk to. Rename the imports to upgrade:

  ```python
  from reflex_build_sdk import AsyncReflexBuild, ReflexBuild, ReflexBuildError
  ```

  The `REFLEX_CLOUD_BACKEND_URL` and `REFLEX_CLOUD_URL` environment variables keep working. ([#7201](https://github.com/reflex-dev/reflex/issues/7201))

### Features

- The client reads its URLs from `REFLEX_BUILD_BACKEND_URL` and `REFLEX_BUILD_URL`, falling back to `REFLEX_CLOUD_BACKEND_URL` and `REFLEX_CLOUD_URL`, which `reflex-hosting-cli` reads. Set both names when the SDK and `reflex deploy` should reach the same backend, since the CLI does not read the `REFLEX_BUILD_*` names. ([#7201](https://github.com/reflex-dev/reflex/issues/7201))


## v0.0.1 (2026-09-18)

### Features

- Add the `reflex-build-sdk` package: `ReflexCloud` and `AsyncReflexCloud` clients for the Reflex Cloud API, starting with `auth.me()` and access token management (`auth.tokens.create/list/delete`), with typed models, typed errors, and retries for requests that are safe to repeat. The async client sends requests with aiohttp and the sync client with httpx; pass a transport from `reflex_build_sdk.transports` to configure or replace the HTTP library. ([#7166](https://github.com/reflex-dev/reflex/issues/7166))
- Add app, secret and project management to `reflex-build-sdk`: `client.apps` (list, search, get, create, delete, start, stop, pause, scale, rollback, deployment history, and runtime logs as an iterator), `client.apps.secrets`, and `client.projects` with its roles and members. ([#7169](https://github.com/reflex-dev/reflex/issues/7169))
- Deploy apps with `reflex-build-sdk`: `client.deployments.create` streams a build's archives to storage and submits the deployment, and `client.deployments.wait` follows it until it is running or awaiting approval, raising `DeploymentFailedError` with the failure report if it fails, or `DeploymentTimeoutError` when the timeout passes first. The client also reads deployment status, reports and build logs, lists regions and machine sizes, and reserves hostnames with `client.apps.reserve_hostname`. ([#7172](https://github.com/reflex-dev/reflex/issues/7172))
- Log in and review code with `reflex-build-sdk`: `client.auth.begin_login` and `finish_login` run the browser login, and the public `reflex_build_sdk.credentials` module loads, saves and deletes the token `reflex login` shares. `client.security_reviews` submits source code for a security review and waits for the result. `client.providers` reads Google Cloud deploy status, connected provider accounts and the Cloud Run manifest, `client.apps` sets an app's hosting provider, full deploy and instance bounds, `client.deployments.check` validates deployment settings before a build, and `client.auth.me` takes a `source` for login analytics. ([#7175](https://github.com/reflex-dev/reflex/issues/7175))
- Manage more of an app with `reflex-build-sdk`: `client.apps` renames, describes and moves apps, sets instance persistence, the rollout strategy, the Cloud Run service name and the weekly report, and reads an app's lifecycle status and running deployment. `client.apps.domains` adds, checks and removes custom domains. ([#7180](https://github.com/reflex-dev/reflex/issues/7180))
- Deploy through environments with `reflex-build-sdk`: `client.apps.environments` enables, lists, creates, updates, reorders and deletes an app's environments, promotes a version to the next one and copies missing secrets. `client.apps.database` creates, reads and deletes an app's managed Postgres database. ([#7181](https://github.com/reflex-dev/reflex/issues/7181))
- Sign an app's users in with `reflex-build-sdk`: `client.apps.sign_in` enables and disables sign-in with Reflex accounts, sets who may sign in, manages invitations, and lists, exports, blocks and unblocks the app's users. ([#7182](https://github.com/reflex-dev/reflex/issues/7182))
- Manage project access with `reflex-build-sdk`: `client.projects` renames and deletes projects and reads audit logs, `projects.roles` creates, updates, previews and deletes custom roles, `projects.members` removes members and reads a member's effective permissions, and `projects.teams` lists, grants and revokes organization teams' roles. ([#7183](https://github.com/reflex-dev/reflex/issues/7183))
- Manage an organization's Google Cloud and your tokens with `reflex-build-sdk`: `client.providers` connects and disconnects Google Cloud and lists the apps blocking removal, and `providers.gcp_connections` adds, updates, verifies, rotates keys of, sets the default of and removes connections. `client.auth.tokens` revokes and refreshes tokens and assigns them to service accounts, and `client.usage` reads the plan allowance balance and usage history. ([#7184](https://github.com/reflex-dev/reflex/issues/7184))
- Publish the SDK as `reflex-build-sdk`, imported as `reflex_build_sdk`. ([#7191](https://github.com/reflex-dev/reflex/issues/7191))
- Call third-party services from an app with `reflex-build-sdk`: `client.apps.connections` reads a live credential for the app or for one of its users, lists what is connected, starts a connection and disconnects it, without the app ever holding the provider's key. `APIStatusError.code` now carries the condition the API names for a refusal, such as `not_connected`. ([#7192](https://github.com/reflex-dev/reflex/issues/7192))
