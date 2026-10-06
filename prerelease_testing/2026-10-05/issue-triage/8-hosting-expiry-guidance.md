Published `reflex-hosting-cli==0.1.73a1` omits expiry/recovery guidance when an explicitly supplied token is rejected during initial authentication. The same API expiry response after initial authentication does include `reflex login` guidance.

This is a **message/documentation boundary**, not an authentication failure: the initial rejection correctly exits nonzero, avoids interactive login with `--no-interactive`, produces no JSON document, and preserves a different stored token.

### Reproduce with the retained local HTTP fixture

Use the [tooling probe](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/tooling/probe.py) and [credential-path adapter](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/tooling/cli_entry.py) from the published-package campaign. The probe starts a loopback HTTP API, redirects the credential file to a temporary directory, and supplies a fictional `REFLEX_ACCESS_TOKEN`; it does not contact a live cloud account.

Run from a neutral directory through an isolated environment containing the [published alpha pins](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/inventory/alpha-requirements.txt):

```sh
env -u PYTHONPATH uv --no-config run --no-project \
  --python /private/tmp/reflex-alpha/bin/python \
  python /path/to/tooling/probe.py --output /private/tmp/tooling-results.json
```

The `expired` scenario executes `reflex cloud apps list --json --no-interactive`. The real SDK sends `POST /api/v1/authenticate/me?source=reflex-enterprise`; the fixture returns HTTP 401 with `{"detail":"Token has expired"}`.

Actual exit status: 1, stdout empty. CLI stderr, excluding the `uv` wrapper warning:

```text
The access token from the REFLEX_ACCESS_TOKEN environment variable was rejected:
access denied (auth request id: <id>)
```

Neither the API expiry sentence nor a `reflex login` hint is present. The other stored credential remains unchanged.

The `expires_after_auth` scenario accepts the same fictional token at `/authenticate/me`, then returns the same HTTP 401 body at `/apps/<id>/stop`. Its stderr is:

```text
You are not authenticated. Run `reflex login` to authenticate.
```

### Expected behavior / clarification

The changelog says an expired token now suggests `reflex login` wherever it appears (#7207), while #7298 describes retaining the existing whoami-style initial rejection message. Please make initial expiry guidance actionable, accounting for an explicitly supplied environment token, or narrow the changelog guarantee to reflect this boundary.

### Evidence and environment

- macOS, CPython 3.12.1; Reflex 0.10.0a1, reflex-hosting-cli 0.1.73a1, published PyPI installs only.
- [Saved real HTTP sequences, exact commands and outputs](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/tooling/results.json), under `hosting` scenarios `expired` and `expires_after_auth`.
- [Changelog heads](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/inventory/changelog-heads.md) and [tooling report](https://github.com/reflex-dev/reflex/blob/08f29b1d278dd9380ecaebdd0b028c17d7abab1b/prerelease_testing/2026-10-05/tooling/README.md).

No real expired credential, cloud mutation or framework workaround was used. No prior-version runtime comparison was performed for this wording boundary.
