## v0.1.71 (2026-08-28)

### Breaking Changes

- `REFLEX_ACCESS_TOKEN` now takes precedence over the token stored by `reflex login`. Previously the stored token won and the environment variable was consulted only when no token was stored, so exporting it to run a script against a different account had no effect on a machine that had ever logged in — silently, and with no way to tell which credential was in use. Exporting the variable is an explicit choice for that invocation; the config file is ambient state left behind by an earlier login. This changes behavior only when both are present and differ. `reflex cloud whoami` reports which source is in use. ([#6918](https://github.com/reflex-dev/reflex/issues/6918))

### Features

- Added `reflex cloud whoami` and `reflex cloud token`. `whoami` reports the account, org, tier and token source that the CLI is authenticating as, resolving the token against the control plane without ever starting a browser login and without printing the token — it shows a non-reversible fingerprint instead, so two machines can be compared without anyone sharing a secret. `reflex cloud token` takes exactly one of `--print`, `--set TOKEN` or `--clear`: `--print` writes the raw token to stdout for capture (`export REFLEX_ACCESS_TOKEN=$(reflex cloud token --print)`), `--set` validates the token with the control plane before storing it and leaves the previous one in place if it is rejected, and `--clear` removes the stored token, noting when `REFLEX_ACCESS_TOKEN` remains set and will take over. ([#6918](https://github.com/reflex-dev/reflex/issues/6918))
- On the deploy that first lands an app on GCP, `--hostname` now doubles as the app's Cloud Run service name, so the service in the customer's console reads like the app's URL instead of `app-<uuid>`. A hostname the service-name grammar refuses (leading digit, over 49 characters, or the reserved `app-<uuid>` shape) is skipped with a note and the server generates a name from the app name; later GCP deploys never send one, since the name is pinned to the live service. ([#6937](https://github.com/reflex-dev/reflex/issues/6937))
- `reflex deploy` uploads a build's two archives straight to storage, concurrently and with a progress bar for each, instead of relaying them through the control plane. ([#6938](https://github.com/reflex-dev/reflex/issues/6938))
- `reflex cloud deploy` now reports why a deploy failed instead of exiting on a status string: the recorded reason, whether the failure was in your app or on Reflex's side, and the end of the build log when that is what explains it. ([#6948](https://github.com/reflex-dev/reflex/issues/6948))

### Bug Fixes

- The hosting config file (`hosting_v1.json`) is now written atomically. `save_token_to_config` and `delete_token_from_config` opened it with mode `"w"`, truncating it before writing, so a failed write — a full disk, an I/O error, an interrupted process — left an empty file and destroyed the stored access token and selected project. Neither helper reports write failures to the caller (`save_token_to_config` logs a warning, `delete_token_from_config` only a debug message), so this was easy to miss. Both now serialize to a temporary file alongside the target and move it into place, leaving the existing credentials untouched when a write fails. A config that exists but cannot be read is no longer treated as empty either, so `delete_token_from_config` leaves a malformed file alone instead of replacing it; `save_token_to_config` still starts fresh from one, so a corrupt config cannot block re-authenticating. This also covers `reflex login` and `reflex logout`, which share these helpers. ([#6918](https://github.com/reflex-dev/reflex/issues/6918))
- Fix for older reflex versions

### Miscellaneous

- The hosting CLI's logging goes through standard python `logging`. On reflex 0.9 and up it shares the `reflex-base` console and `LogLevel`; on earlier reflex, where `reflex-base` is not installed, the CLI renders the same output itself. Debug output renders purple (was blue), errors go to stderr (was stdout), and success messages are hidden at `--loglevel warning`. ([#6866](https://github.com/reflex-dev/reflex/issues/6866))
- `reflex cloud token --set` accepts the token on stdin — pass `-`, or omit the value entirely — so live credentials need not appear in shell history or the process list. When stdin is a terminal it prompts without echoing. `reflex cloud whoami` writes its output directly rather than through the shared console, which applies rich markup and wraps to the terminal width: identifiers now print in full instead of being truncated to fit, and `--json` stays on one line so it can be piped. ([#6918](https://github.com/reflex-dev/reflex/issues/6918))
- The `reflex deploy` command implementation now lives here, in `reflex_cli.v2.deploy`. The package no longer imports the `reflex` framework at module scope, so it stays importable on its own. ([#6924](https://github.com/reflex-dev/reflex/issues/6924))


## v0.1.70 (2026-08-18)

### Deprecations

- `reflex cloud deploy` is renamed to `reflex cloud gcp-standalone`, deprecated as of 0.1.70 and removed in 0.2.0. Inside the `reflex cloud` group, `deploy` meant the standalone gcloud script runner while `reflex deploy` meant the managed platform deploy — one namespace apart, opposite semantics. The old name still works and is hidden from help; invoking it warns, naming both the new name and the managed path. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))

### Features

- `deploy()` accepts `gcp_connection`, `full_deploy` and `strategy`. `gcp_connection` resolves a named GCP connection and pins the app to it (`provider_account_id` on the provider write), instead of every CLI deploy landing on the organization's default connection. `full_deploy` is written before the hostname is reserved, so the reserve hands back the single provider origin the frontend is then compiled against. All three can also be set in the config file. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))
- `reflex cloud providers list` (also reachable as `providers connections`) now lists each connection's name, default marker and runtime service account, so there is something to pass to `reflex deploy --gcp-connection`. `providers status` lists the same connections. A member who may not read the organization's stored provider accounts still gets the connection names, from the GCP status; their runtime identities are reported as unreadable rather than as the project default. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))

### Bug Fixes

- Optional settings in `cloud.yml` / `pyproject.toml` are validated again on Python 3.10–3.13. A `X | None` annotation reports as `types.UnionType` there, which the config validator did not recognize, so every optional field went unchecked on those versions while being checked on 3.14 — a quoted `full_deploy: "false"` was sent to the server as a truthy string, and a non-string `hostname` or `gcp_connection` failed later with a `TypeError` instead of a config error. ([#6908](https://github.com/reflex-dev/reflex/issues/6908))


## v0.1.69 (2026-08-13)

### Features

- `deploy()` accepts `min_instances` and `max_instances`, which are applied to the app before the deployment is submitted so it picks the new autoscaling bounds up. Only the bounds explicitly passed are sent, so apps keep their platform defaults otherwise. ([#6884](https://github.com/reflex-dev/reflex/issues/6884))

### Bug Fixes

- `--vmtype` is no longer dropped when deploying to Google Cloud. The server maps VM types onto Cloud Run CPU/memory limits, so the flag is now passed through; only `--region` is still ignored for that target, since the region comes from the connected GCP account. ([#6884](https://github.com/reflex-dev/reflex/issues/6884))


## v0.1.68 (2026-08-03)

### Features

- When a deployment requires approval, `reflex deploy` now reports that the build was submitted for approval and will deploy automatically once approved, instead of polling indefinitely. ([#6797](https://github.com/reflex-dev/reflex/issues/6797))
- Token validation requests now send an `X-Request-ID` header, and failed validations print the ID (e.g. `Unable to validate access token: ... (auth request id: ...)`) so it can be quoted to support to correlate the failure with server-side logs. ([#6821](https://github.com/reflex-dev/reflex/issues/6821))
- Added Google Cloud (GCP) as a managed deploy target for `reflex deploy`. When your organization has a GCP account connected (Enterprise tier), `reflex deploy` asks whether to deploy to Reflex Cloud or your GCP account (or pass `--provider gcp` / set `provider: gcp` in your config to skip the prompt), and `reflex cloud providers status` / `list` report the connection state.
- Added `reflex cloud apps rollback DEPLOYMENT_ID`, which rolls an app back to a previous deployment by redeploying its already-built image without rebuilding from source. `reflex cloud apps history` now reports whether each deployment can be rolled back to.
- Added optional per-deployment descriptions (changelog notes): set one at deploy time with `reflex deploy --description "..."`, set or clear it later with `reflex cloud apps describe`, and view it in `reflex cloud apps history`.

### Miscellaneous

- Raised the `rich` upper bound to `<16` (adopting rich 15). ([#6678](https://github.com/reflex-dev/reflex/issues/6678))


## v0.1.67 (2026-06-17)

### Features

- Added a `--service-account` flag to `reflex deploy --gcp`, letting Cloud Run services run as a least-privilege per-service service account instead of the project's default compute SA. ([#6556](https://github.com/reflex-dev/reflex/issues/6556))
- Added `--max-instances`, `--allow-unauthenticated/--no-allow-unauthenticated`, `--env KEY=VALUE`, and `--envfile` flags to `reflex deploy --gcp`, letting you cap Cloud Run autoscaling, deploy a private service, and set environment variables at deploy time. ([#6557](https://github.com/reflex-dev/reflex/issues/6557))
- Added `reflex cloud scan`, which uploads your app source for a Reflex-aware security review and reports security and logic flaws. Supports `--json` output and a `--fail-on` severity gate for CI. ([#6632](https://github.com/reflex-dev/reflex/issues/6632))
