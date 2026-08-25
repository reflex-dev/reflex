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
