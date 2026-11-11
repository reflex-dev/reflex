### Bug Fixes

- The `reflex cloud project list` table shows the project tier name instead of the full tier object. Use `--json` to get the full tier. ([#7340](https://github.com/reflex-dev/reflex/issues/7340))
- Print `reflex cloud apps logs` lines as readable `timestamp [LEVEL] message` text instead of Python dicts. `--json` still prints the structured records, and `--loglevel` no longer hides the log lines. ([#7390](https://github.com/reflex-dev/reflex/issues/7390))
- Show `reflex login` guidance when initial authentication rejects an access token, including instructions to replace or remove an explicit `REFLEX_ACCESS_TOKEN` or `--token` override.
  When `reflex cloud whoami` or a noninteractive cloud command cannot validate a token due to a temporary service or connection failure, suggest retrying instead of replacing credentials. ([#7434](https://github.com/reflex-dev/reflex/issues/7434))
- `reflex deploy` now waits and retries confirmed scaling conflicts with progress messages, reusing the uploaded build and preserving support for custom backend URL prefixes. It stops on unrelated failures and uncertain writes, and warns when bounds may remain changed after a failed deployment, including server errors and unreadable success responses. ([#7463](https://github.com/reflex-dev/reflex/issues/7463))
- Authentication validation now reports the HTTP status when the control plane refuses the request, and only suggests trying again later for failures that may succeed on retry (timeouts, HTTP 429 and server errors). ([#7546](https://github.com/reflex-dev/reflex/issues/7546))

### Performance

- Speed up non-interactive deploys by skipping the provider availability request used only for the interactive provider prompt. ([#7452](https://github.com/reflex-dev/reflex/issues/7452))
