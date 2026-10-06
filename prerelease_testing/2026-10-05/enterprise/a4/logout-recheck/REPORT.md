# Fresh published-a4 logout reassessment

**Enterprise #245 remains a conditional security blocker on the current PyPI
0.9.7a4 wheel.** This follow-up was executed after the maintainer challenged the
earlier evidence. It uses a completely fresh installation, checks the installed
package against the published wheel, and completes the account changes without
manually clearing browser cookies. Ordinary logout passes. An application
default-factory failure still leaves protected data available to a subsequent
authenticated identity on the same Reflex client session.

The mixed-version Redis finding is separately reclassified as an expected,
unsupported configuration under the maintainer's forward-only upgrade policy;
see [its disposition](../rolling/DISPOSITION.md). It is no longer a blocker.

## Publication and execution provenance

The [current PyPI metadata](evidence/current-release-metadata.json) contains
0.9.7a1 through a4, with no newer 0.9.7 alpha observed. The tested a4 wheel was
uploaded at **2026-10-06 04:37:42 UTC**, before this fresh run at
**2026-10-06 05:22:39 UTC**. Its SHA256 is
`a1c8d0e7977b6a39590dd8dcaa423bc486666d7fdd79134de4ffee6afb1b3638`.
This is the same published artifact as the preceding a4 archive audit, not an
earlier a2/a3 install or a checkout build.

A new isolated environment was installed from PyPI with `uv --no-config pip
install --only-binary :all: --refresh` and the exact 104-package alpha graph.
All **157** installed `reflex_enterprise/` package files match the freshly
downloaded wheel byte for byte. Reflex, reflex-base and enterprise import from
that environment; no direct-URL installations or `PYTHONPATH` overlays are
present. Reflex/base are 0.10.0a1 and enterprise is 0.9.7a4.
[Provenance and installed cleanup functions](evidence/publication-and-provenance.json),
[install log](evidence/install.log), [exact graph](requirements-lock.txt) and
[dependency check](evidence/pip-check.log) are retained.

The app ran through the public CLI in a neutral temporary directory with an
owned fictional OIDC provider, Bun 1.4.2 and Playwright 1.55/Chromium 140.
`CI=true` bypasses the cloud entitlement prompt for this local auth test; the
AuthPlugin and actual local OIDC exchange remain active. Application factories
simulate a recoverable dependency outage; no framework/auth implementation,
installed distribution or browser asset is patched. Ports 3152/8152/9151 were
closed before the run and are closed after owned-process cleanup.

## Completed browser observations

| Case | Logout | Previous frontend record after next login/reload | Previous backend cache after next login/reload | Anonymous protected mutations |
| --- | --- | --- | --- | --- |
| Ordinary control | Completes, including provider end-session | Absent | Absent | None |
| Frontend factory unavailable | Reports cleanup error | Present under the new authenticated identity | Absent | None |
| Backend factory unavailable | Reports cleanup error | Absent | Present under the new authenticated identity | None |

All three cases completed. Each handoff uses the same recorded client-token
fingerprint, a normal OIDC login and an explicit page reload with a checked new
identity. The application dependency is restored before the next login.
**No case manually clears browser cookies.** The private-data markers belong
only to fictional local test accounts. The independently recorded protected
action log shows no anonymous mutation; the action redirects to login after
logout, and the next authenticated actor is the new account.

[Per-case results and browser/network observations](evidence/browser-results.json),
[independent action log](evidence/actions.jsonl), [server output](evidence/server.log),
[provider output](evidence/provider.log) and [completion/cleanup](evidence/run-status.json)
retain the measurements. The frontend and backend [screenshots](evidence/screenshots/)
were visually reviewed against their saved fields. There are no captured page
exceptions or HTTP-error responses. Cookie-sync `net::ERR_ABORTED` notifications
remain: three in the normal control and two in each failure case. Their cause
is unresolved and they are not treated as proof of the confidentiality failure.
Synthetic token material in the provider log is redacted; see
[redaction counts](evidence/redactions.json).

## Why the published try/except does not complete this reset

Inspection of the installed wheel confirms the new handler exists. Its scope
is a whole protected State, rather than recovery of a failed field restoration:

- `reset_app_state` catches `_reset_protected` errors, continues to other
  protected States, then re-raises the first reset error.
- `_field_default` calls an application field's default factory. If it raises,
  `_reset_protected` does not replace that field's existing value or finish the
  remaining cleanup of that State, including its computed-cache invalidation.
- OIDC `_reset_plugin_owned_state` awaits `reset_app_state` before resetting
  normalized `AuthUserState`. An exception prevents that later cleanup step.

This explains the measured distinction: continuing other State resets clears
the unaffected store, while the failing store survives. It does not establish
an anonymous authorization bypass, universal logout failure or a newly
introduced a4 regression. The user's security criterion independently applies
to the demonstrated account-boundary confidentiality weakness.

## Patch requirements and review limits

Guarantee authentication/identity/cookie cleanup despite application reset
errors, while reporting failure accurately. Discard or quarantine a State tree
whose protected fields cannot be restored before admitting another identity;
continuing other resets or swallowing the exception is insufficient. Rebuild
fresh state or verify complete reset before reusing the client session. Add
regression checks for frontend and backend factory failures followed by account
change, including ordinary logout and anonymous-action denial controls.

These are requirements for a maintainer's patch, not an untested implementation.
No framework fix or GitHub issue/comment was made in this follow-up.

Adversarial review: **1.** Each case is one fresh local run, using a fictional
provider and an explicitly induced application dependency failure; all IdPs and
failure modes are not covered. **2.** This is a single-process development run,
not production/Redis/multi-worker logout validation. **3.** No older security
baseline establishes the introducing release. **4.** The driver asserts case
completion; its exit status alone does not mean security passed. The per-case
identity, retained-data, action-log and token fields were separately inspected.
**5.** Earlier cookie-clearing evidence and its independent review remain
historical; this new no-clearing run is root-reviewed and separately retained.

## Reusable artifacts

[Controller](source/validate.py) checks published bytes, launches owned services,
runs the [new browser driver](source/drive_recheck.py) and stops its processes.
The app-owned dependency markers and paths are confined to its neutral app
directory. The [app](source/app/security_probe/security_probe.py),
[fictional provider](source/mock_oidc.py) and [retained helper](source/retained_driver.py)
are saved as executed. The old helper's main driver is not invoked. Copy these
sources into a neutral directory with their recorded temporary paths when
reusing them; install the lock from published PyPI packages in a new environment.
Create empty `logs/` and `screenshots/` directories in that neutral root before
launching the controller. Run with `PYTHONPATH` unset and the existing browser
runtime selected by `PLAYWRIGHT_BROWSERS_PATH`; the controller's required
`--output` argument selects the evidence destination.
