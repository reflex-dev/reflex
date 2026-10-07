CLUSTER: thirdparty_a2
SUMMARY: 10-07 re-run of the third-party sweep on reflex 0.10.0a2 in dev, prod and prod+redis with 0.10.0a1 and 0.9.12 baselines: the 22-package install/import sweep (py3.11-3.14), tp_components and tp_patterns in the browser, the reflex-local-auth demo + an AppHarness test, magic-link, google-auth, global-hotkey, plus explicit re-verification of the 12 10-06 thirdparty findings. Everything behaves exactly like a1 and 0.9.12. F-003 and F-004 FIXED, F-001 CHANGED (documented and loud, enterprise half fixed), F-007/F-008/F-009/F-010/F-011/F-012/F-013/F-014/F-018 unchanged. New regressions from the #7461 fix: class-level monkeypatching of State var defaults cannot be undone (N-039) and assignment to an unannotated None placeholder raises / executes callables (N-040). Pre-existing: AppHarness second app loses shared-package handlers (N-041), prod build fails with monaco/webcam/clerk pages (N-042), py3.14 ignores rxconfig state_auto_setters in the worker (N-043).
ARTIFACTS: prerelease_testing/2026-10-07/thirdparty_a2/ (NOTES.md with per-finding table, rerun commands and layout index; apps/, harness/, drivers/, probes/, pytest_probe/, bin/, logs/, out/; ~5 MB)
TESTS:
- [pass] install/resolution of 22 packages on a2 (112 packages, matches a2-freeze.txt); dry-runs only add packages; no package caps reflex; greenlet added (N-001).
- [anomaly] import sweep 20/22 on a2 (3.11-3.14), a1, 0.9.12: reflex-chakra and community reflex-ag-grid fail identically everywhere.
- [pass] tp_components dev 29/35 (6 failures identical on a1/0.9.12; console identical to a1); [anomaly] prod build fails with monaco/webcam/clerk (N-042); with those skipped 31/34.
- [pass] global-hotkey dev+prod; intersection-observer, pyplot, motion, type-animation, image-zoom, color-picker, qrcode, simpleicons, chat render and interact dev+prod.
- [anomaly] reflex-chat initial_messages leak (F-009) + React "order of Hooks" console error on all versions.
- [pass] reflex-local-auth demo 36/38 in dev, prod, prod+redis (2 failures identical on a1/0.9.12); AppHarness test 2/2 on a2, a1, 0.9.12; hot reload while logged in 7/7.
- [pass] magic-link 10/11 dev/prod (rx.moment bounce identical everywhere); real prod rejects submit without captcha.
- [pass] google-auth dev+prod: bogus token cleared from localStorage on a2 (a1 kept it), does not unlock /protected.
- [pass] fresh-profile storage check on the three auth demos: no default write-back on a2 or a1.
- [pass] tp_patterns dev/prod/prod+redis: mixins, subclass of package base state, get_state/get_value/setvar, event_handlers reuse, add_var, type() substates, substate redeclare; mixin computed-var override honoured on a2/a1, ignored on 0.9.12.
- [pass] F-003 repro: 9 dev seeds, prod seeds 0/4, prod+redis; cvstore a/b/e_cookie/e_session/f/g pass on a2, fail on a1; 0.9.12 seed-dependent.
- [pass] F-004 e2e (ClassVar variant) dev/prod/prod+redis: survives serialization, instance writes, reset(), reload.
- [anomaly] F-001 core: class reads return Field for every pattern; f-strings raise BackendVarFormatError at compile (10-06 e2e app no longer starts).
- [anomaly] reflex-clerk set_clerk_session with a valid RS256 JWT: TypeError 'Field' object is not iterable on a2/a1; 0.9.12 validates.
- [pass] removed-names / breaking-change probe identical to a1; `reflex component` exits 2 cleanly, no longer in --help.
- [fail] N-001 via packages: fresh a2 + reflex-local-auth + reflex-magic-link-auth has sqlalchemy 2.1.3, no greenlet; imports/db migrate/compile die.
- [anomaly] N-039 monkeypatch teardown TypeError + leak (a2 only); N-040 None-placeholder assignment TypeError + callable executed (a2 only).
- [anomaly] N-041 second AppHarness app loses shared handlers; N-043 py3.14 state_auto_setters ignored in worker (all versions).
- [skipped] real Google/Clerk logins, reCAPTCHA, lamejs, Monaco assets (sandbox/credentials).
REVERIFIED:
- F-001 changed; F-003 fixed; F-004 fixed; F-007 still broken (Linux npm SIGTERM); F-008 still broken (1.2 M chars → 723 socket cycles); F-009 still broken; F-010 still broken; F-011 still broken; F-012 still broken; F-013 still broken; F-014 still broken (message gap); F-018 still broken (3/3 on a2/a1, 0/3 on 0.9.12).
ISSUES:
- N-039 (MEDIUM, regression vs a1), N-040 (MEDIUM, regression vs a1 and 0.9.12) — verifier running.
- N-041, N-042, N-043 (LOW, pre-existing).
NOT_COVERED: real OAuth logins; CDN-dependent assets; reflex-chakra and community ag-grid pages (no import); enterprise AG Grid (reverify_core/ent_grid); F-017, F-002/F-005/F-006/F-015/F-016 (other clusters); 3.11/3.13 beyond the import sweep; macOS. Servers stopped; 3500-3519/8500-8519 free.
