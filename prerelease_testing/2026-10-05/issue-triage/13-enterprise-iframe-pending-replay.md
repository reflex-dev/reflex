With published enterprise `0.9.7a3`, the combined flow of an anonymous protected event inside an iframe followed by popup login authenticates successfully, but does not automatically return the child to its original page or replay the event. This reproduces on both Reflex `0.10.0a1` and `0.9.12` with default OIDC scopes.

This is **shared with stable**, not a demonstrated new Reflex-alpha regression. No a2 baseline was run for this newly combined flow. It is separate from #230's popup **logout** problem: this report concerns popup **login** and the originating child's pending event.

### Reproduce

Use the saved [auth_min app](https://github.com/reflex-dev/reflex/tree/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/apps/auth_min), [local OIDC provider](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/mock_oidc.py) and [startup commands](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/REPORT.md#reproduction-and-cleanup). Copy fixtures into a neutral directory and use isolated PyPI-only UV environments. Leave `AUTH_TEST_EXTRA_SCOPES` unset for the failing configuration.

The public `/` page has a protected `@rxe.event` Reveal handler that resolves `AuthUserState.current()` and sets `message = "revealed-" + user["sub"]`. Public `/iframe` embeds it using `rx.el.iframe(src="/")`.

1. In a fresh anonymous browser context, open `http://localhost:3132/iframe`.
2. Click Reveal **inside the child iframe**, before logging in. The child redirects to `/login?redirect_to=%2F`, and `rxe_auth_pending_event` contains `ProfileState.reveal`.
3. Click Login with Generic in the child; authenticate Alice in the popup and let the popup close.
4. Expected: the child returns to `/`, replays the saved event, displays `revealed-alice`, and consumes pending-event storage.
5. Actual: the child stays on `/login?redirect_to=%2F` with only Sign in/Login with Generic visible. The pending event remains after an additional ten seconds.
6. As a diagnostic, explicitly navigate that same child frame to `/`: the event then replays and storage is consumed. This is not a framework fix.

### Controls and diagnostics

- Default-scope alpha enhanced driver: **3/4 flows pass**; the combined iframe flow fails. Three additional focused fresh-context repeats also fail; manual child navigation recovers **3/3**.
- An inert message observer confirms the child receives `post_auth_generic` from the app origin after popup authentication. Thus the observed failure is automatic return/replay, not proof that login failed or the stored event is unusable.
- Stable Reflex `0.9.12` + the same a3 wheel: **3/4 enhanced flows pass**, with the same child URL and pending event in the failing combined case.
- Ordinary top-level anonymous pending replay and direct iframe popup login followed by Reveal pass. The combined alpha case also passes when `extra_scopes=["offline_access"]`; that extra-scope stable combination was not rerun.
- No page or HTTP errors accompany the failing case; aborted cookie-sync requests are preserved separately. No authorization bypass is demonstrated.

### Environment and saved repros

macOS arm64, CPython 3.12.1, Bun 1.4.2, Playwright 1.55.0 / Chromium 140.0.7339.16, fictional Alice/Bob accounts at a local provider.

- [Exact alpha graph](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/requirements-lock.txt) and [stable graph](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-stable/requirements-resolved.txt).
- [Enhanced driver](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/drive_auth_min.py), [focused repeat/recovery driver](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/recheck_iframe.py) and [message/storage/recovery observations](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-alpha/logs/iframe-repeat.json). The focused observer records failed results without a nonzero exit; read its JSON fields. The enhanced matrix exits nonzero on failure.
- [Stable browser evidence](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-stable/evidence/auth-min-default-browser.json) and [stable reproduction instructions](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/auth-stable/README.md).

No framework source was changed. This is local development-mode OIDC testing; production auth and external IdPs were not exercised for this flow.
