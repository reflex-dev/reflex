## v0.1.67 (2026-06-17)

### Features

- Added a `--service-account` flag to `reflex deploy --gcp`, letting Cloud Run services run as a least-privilege per-service service account instead of the project's default compute SA. ([#6556](https://github.com/reflex-dev/reflex/issues/6556))
- Added `--max-instances`, `--allow-unauthenticated/--no-allow-unauthenticated`, `--env KEY=VALUE`, and `--envfile` flags to `reflex deploy --gcp`, letting you cap Cloud Run autoscaling, deploy a private service, and set environment variables at deploy time. ([#6557](https://github.com/reflex-dev/reflex/issues/6557))
- Added `reflex cloud scan`, which uploads your app source for a Reflex-aware security review and reports security and logic flaws. Supports `--json` output and a `--fail-on` severity gate for CI. ([#6632](https://github.com/reflex-dev/reflex/issues/6632))
