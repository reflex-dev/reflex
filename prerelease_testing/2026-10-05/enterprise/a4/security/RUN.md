# Maintainer validation setup

The app and executed drivers use the fixed neutral root
`/private/tmp/reflex-enterprise-a4-20261005-security`, ports 3152/8152 and provider
9151. The test environment is
`/private/tmp/reflex-enterprise-a4-20261005-security-venv`. These paths must be
preserved or deliberately adapted together when reusing the fixture. The
provider copied here is the exact executed local provider; the existing
`sha256.json` records the previously collected 50-file payload, before this
setup document/provider were added by the root reviewer.

Install [requirements-input.txt](requirements-input.txt) into a fresh isolated
UV environment from PyPI, using `--no-config`, `--index-url
https://pypi.org/simple` and `--refresh-package reflex-enterprise`. Copy `app/`,
`mock_oidc.py`, and the desired driver into that neutral root, excluding generated
files. Create `logs/` and `screenshots/` there. Keep the explicit Bun 1.4.2 path
in the config; use published Playwright with the private Chromium installation.

Run the copied provider through that isolated interpreter in a separate terminal.
From the copied `app/` directory, the actual development server environment is:

```sh
env -u PYTHONPATH CI=true AUTHLIB_INSECURE_TRANSPORT=1 OIDC_ISSUER_URI=http://localhost:9151 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret uv --no-config run --no-project --python /private/tmp/reflex-enterprise-a4-20261005-security-venv/bin/python reflex run --frontend-port 3152 --backend-port 8152 --loglevel debug
```

Use the retained `drive_faults.py` only against this owned fictional local app for
defensive regression validation. Its exit status establishes completion, not the
absence of a weakness; inspect the structured observations and compare the
normal control. The separate `check_mcp_security.py` is explicitly incomplete
and must not be used as a passing acceptance gate without follow-up work.

Stop the owned CLI/provider processes and verify ports 3152/8152/9151 are closed.
Do not install from the testing checkout, change installed package code, or
reuse real credentials. [REPORT.md](REPORT.md) and [REVIEW.md](REVIEW.md) state
the completed evidence, caveats and recommended patch requirements.
