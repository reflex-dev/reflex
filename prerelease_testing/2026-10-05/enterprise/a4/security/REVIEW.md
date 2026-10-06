# Independent defensive review of logout-fault evidence

The existing a4 evidence supports **confirmed cross-account protected-state disclosure after incomplete logout cleanup**. This meets the security-weakness blocker criterion independently of whether a4 introduced the defect. It does not establish an unauthenticated authorization bypass or universal remote access to another user's session.

This review read the saved app/driver, `logs/faults-a4.json`, the app traceback log and Bob screenshots from the neutral security tree, plus the published a4 cleanup/identity code. No additional browser operation, attack testing, server start, framework change or external action was performed. The reviewed `enforcement.py`, `oidc/state.py` and `user_state.py` match the independently installed a4 auth-lane files byte-for-byte.

## Evidence that distinguishes disclosure from stale UI

- Normal control: Bob's identity is displayed, the record is empty, and the protected cache is empty. No Alice marker is recorded during the Bob-login stage.
- Frontend-default failure: after normal Bob OIDC login and a fresh `/profile` document navigation, the helper explicitly asserts identity `bob`. The resulting snapshot and screenshot show Alice's prior private record. Newly received WebSocket frames during the Bob-login stage also contain that record marker. An independent action audit records a permitted action as Bob, not Alice.
- Backend-default failure: the equivalent Bob snapshot and screenshot show Alice's prior protected-cache value. Newly received WebSocket frames during the Bob-login stage contain that cache marker. The frontend record has reset successfully, separating this failure from the frontend-default case.
- The same Reflex client-token fingerprint persists through each account transition. Full document navigation and server-frame evidence support surviving server state being delivered again, beyond merely retaining Alice's old DOM. The wire log labels the whole login interval; it does **not** establish exact frame ordering relative to Bob's identity assertion.

## Material caveats

1. Both fault cases require an application default factory to raise during cleanup. The fixture uses ordinary application factories and app dependency failures, without modifying auth internals. This is an exceptional cleanup path, not normal logout behavior.
2. The driver manually clears browser cookies, recovers the application dependency, and then performs normal Bob OIDC login while retaining the same Reflex client token. Therefore the evidence does not prove failed logout cleared browser cookies or completed provider logout. The retained cookie metadata actually shows token cookies after the fault.
3. Protected actions after the failed logout and after forced-anonymous navigation produced no recorded anonymous mutation and redirected to login. Anonymous snapshots withheld private markers. The security finding is disclosure to a subsequently authenticated different account on surviving state, not proof that anonymous users can act as Alice.
4. The fields use default authentication protection, which allows authenticated callers; no application owner-specific authorization check was configured. The framework's own reset contract is intended to prevent prior-user state surviving into the next identity. Applications with stricter owner checks may reduce exposure. The test uses synthetic confidentiality markers, one observed run per fault mode, a local provider and a development server; Redis, separate-browser access and other provider behavior are not established here.

## Source-supported failure path and patch requirements

Published `OIDCAuthState._reset_session` clears provider state, then calls plugin cleanup. Plugin cleanup awaits `reset_app_state` **before** resetting normalized `AuthUserState`. The sweep attempts other substates, but raises after a reset failure. `_reset_protected` calls application default factories; a raising factory prevents assignment of that field and skips remaining cleanup in that substate, including protected computed-cache invalidation. The later normal identity update can request protected-state redelivery from the surviving tree. These mechanisms agree with both recorded fault cases.

Required fail-closed behavior:

- Complete local credential and normalized-identity revocation, including browser cookie synchronization, independently of application reset exceptions. Preserve an accurate failure audit without making revocation depend on a successful default factory.
- Discard, invalidate or quarantine any state that failed cleanup before accepting a new identity on that client state. Failed cleanup must prevent prior private values from being serialized, read or authorized merely because a different user is now authenticated. A blanket `finally` around identity reset alone does not solve retained private data.
- Continue independent field/cache cleanup safely, and invalidate protected computed caches even when another field's reset fails. If no safe fresh value can be constructed, deny access to the affected state until recovery; arbitrary type-incompatible fallback assignments are not a sound substitute.
- Bind usable private state to the current identity/session generation and reject reuse of an uncleared prior generation. Defensive regression acceptance should cover both frontend and backend factory failures, fresh-document reload and a different legitimate identity: no old private value may reappear, while anonymous actions remain denied.

No source fix or further test was made. The security lane retains the exact raw evidence and owns final cleanup/provenance collection.
