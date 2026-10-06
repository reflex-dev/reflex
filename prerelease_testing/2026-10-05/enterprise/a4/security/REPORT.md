# Published a4 defensive security review

**A conditional cross-user confidentiality weakness is confirmed.** With published enterprise **0.9.7a4** and Reflex/base **0.10.0a1**, an ordinary application default factory failing during logout can leave the previous user's protected frontend record or backend cache available to the next authenticated user on the same Reflex client token. This is concrete evidence for the existing open [issue #245](https://github.com/reflex-dev/reflex-enterprise/issues/245), rather than an inference from an exception alone.

| Completed app scenario | Anonymous protected mutations | Bob's subsequent private data |
| --- | --- | --- |
| Normal logout control | None | Empty defaults; no Alice data |
| Frontend default-factory outage during logout | None | Alice-owned private record displayed while identity is Bob |
| Backend default-factory outage during logout | None | Alice's private cached value displayed while identity is Bob |

Each scenario used real OIDC login/logout, browser events, protected getters and an independent app mutation log. The same hashed client token was preserved through the Alice-to-Bob handoff. The failing factory was user application code simulating an unavailable default dependency; no auth/framework internals were patched. Unaffected protected states continued resetting. Failed logout left four OIDC cookie values in the test browser, whereas normal logout cleared them. A subsequent protected action redirected to login and produced no mutation. Browser page errors and HTTP responses >=400 were absent from the app scenarios; navigation-related aborted cookie-sync requests and the expected server factory tracebacks are retained.

**Precondition and evidence limit:** the completed handoff explicitly cleared the owned test context's cookies and restored the app dependency before Bob's login. Direct normal account switching without this intervention was not completed. The measurements establish retained confidential state reaching a different authenticated identity once the same client resumes; they do not establish an unauthenticated bypass, an attacker-controlled trigger, or universal ordinary-flow exposure. No critical-severity or newly introduced a4 regression is established. The a3 published environment was prepared and verified, but its browser comparison was stopped when the review scope was narrowed. The known issue predates a4.

The installed a3/a4 app-reset and provider-reset routines have identical ASTs ([source comparison](evidence/reset-source-comparison.json)); this supports the existing-issue classification but does not replace the missing runtime baseline.

For release triage, this is a **must-address fail-closed boundary where applications can experience cleanup failures and reuse a browser/client session**. The impact is disclosure of another user's session data, not merely failed logout UI. Treat it as a conditional confidentiality defect; the root release review should decide the blocker classification using the user's policy and these stated limits.

## Recommended patch design

- Separate identity/session revocation and browser credential clearing from fallible application cleanup. Guarantee their completion even when default factories, setters or state loading fail; retain a failure signal and audit entry.
- Quarantine or discard a client State session that cannot be reset. Do not bind a new authenticated identity to the failed session's protected frontend fields, backend values or computed caches. Resume only with a safely initialized state/session, or fail reauthentication until recovery succeeds.
- Keep attempts to reset other states, but do not mistake partial cleanup for a safe account boundary. Handle failures before protected data can be redelivered to a new identity.
- Add real browser regressions for normal account switching after frontend/backend factory failure, unchanged client-token/session identity, explicit-cookie-independent logout recovery, denied anonymous actions, cached-var clearing and later successful login. Cover state-load and setter failures separately, plus supported Reflex versions.

No framework changes are included here.

## OAuth/MCP observations and limits

The partial wire run completed real Alice and Bob OAuth consent/exchanges with opaque app-issued tokens; authorization-code replay returned 400. Missing, invented and unsigned-JWT bearer credentials returned 401. An anonymous bearer carrying caller-supplied identity/session claims could not run the protected event or read the protected custom MCP resource; it saw only default public/placeholder state, with router token/session identifiers blanked. Framework logout handlers were absent from event search.

The driver stopped on an incorrect assumption that this transport issued an MCP session identifier; the SDK returned `None`. The prepared cross-bearer transport-session request and final Bob SDK read did **not** execute and are not passing checks. The completed Alice branch reached its protected-resource assertion, but its full response was not persisted before the driver stopped. No additional security simulations were run after the defensive scope clarification. Pending-action observations showed no anonymous mutation; where replay executed, the recorded actor was Bob. They do not establish comprehensive pending-event behavior across identity changes.

## Artifact and isolation record

[`app/`](app/) and the retained executed drivers are the local reproduction sources. [`evidence/faults-a4.json`](evidence/faults-a4.json), screenshots, server/provider logs and the app action log preserve the actual app outcomes. [`evidence/mcp-security.json`](evidence/mcp-security.json) and its driver failure log distinguish completed wire checks from the interrupted comparison. Auth codes/tokens and cookie values are not published in the evidence; session tokens are hashed.

The fresh PyPI-only environments contain the exact **104-package** alpha graph, changing only enterprise a3 to a4. Both import-provenance files assert isolated site-packages, exact pins, absent `PYTHONPATH` and no direct/editable installs. All execution used `uv --no-config run --no-project --python <exact-env>/bin/python` from neutral `/private/tmp` directories. Existing explicit Bun **1.4.2** and private Chromium **140.0.7339.16** were used. Generated app requirements, external assets, lock/build directories and caches are excluded from saved sources. All owned ports **3152/8152/9151** are released. No framework/source installs, repository tests, external comments/issues or commits were made.
