# Release plan after the 0.10.0a5 pass (reflex / reflex-base 0.10.0a5 + reflex-enterprise 0.9.7a5)

**Status: FINAL.** Final pre-release pass: every identified-and-fixed regression of the 0.10 train was re-run from its
original repro with the broken version as a positive control, and the three a5 changes were hunted end to end by three
agents plus an independent verifier. Evidence: [FINDINGS.md](./FINDINGS.md). Supersedes
[../2026-10-08-a4/RELEASE_PLAN.md](../2026-10-08-a4/RELEASE_PLAN.md). Rubric (testing skill): fix before release =
confirmed regression vs the previous stable (0.9.12), security-relevant, significant user impact, or trivially small.

## Every identified-and-fixed regression stays fixed on a5
F-002, F-003, F-004, F-005, F-006, F-014, N-001, N-004 (as documented), N-005, N-008, N-025, N-032, N-039, A3-01, A3-02,
A3-04, A3-11, A3-12 — each re-run on a5 from its original repro, with the broken version (a1 / a3, or the earlier pass's
recorded result) reproducing first. In-place upgrades 0.9.12 → a5 and a4 → a5, the third-party sweep, the auth packages
and the enterprise demos equal the a4 pass. Packaging: 20/20 published, `.pyi` audit PASS, wheels byte-identical to the tag.

**#7360 (security) is verified:** a4 leaks cookies (incl. HttpOnly enterprise `_oidc_*` tokens) and 8 credential headers
into websocket frames and the DOM; a5 sends none of them to the browser in dev, prod and prod + Redis, while every
backend `self.router` read (on_load variants, redirects, dynamic routes, client nav, Redis workers, enterprise page guards
and deep-link login) is unchanged from a4.

## Fix before release
- **A5-01** (MEDIUM, regression vs 0.9.12 and a4, verified) — #7519 snapshots a mutable class-body default when the class
  is created, so a module-level list / dict / config object populated after the `class` statement (registry, plugin,
  lifespan-loaded config, `mock.patch.dict` in tests) is silently empty in every session; `rx.field(value)` stays live, so
  the two spellings now differ. Not in the changelog, docs or upgrade guide; no review thread or test covers it. Reach looks
  low (no hit in GitHub code search, reflex-examples, 38 downstream wheels, enterprise) but the failure is silent.
  Small fix: keep live semantics for class-declared defaults in `_default_arguments` and copy up front only in
  `Field.set_default` / `add_var` (which is what #7519's rationale needs). The same fix resolves A5-02 (opaque pickle
  error instead of the `VarTypeError` naming the var) and A5-04 (extra import-time copy of large defaults). If the
  snapshot is intended instead, it needs a breaking-change line and an upgrade-guide note — maintainer decision.
- **A5-05** (LOW, docs, trivially small) — the upgrade guide's "On 0.9, assigning
  `State.__fields__["items"].default = []` was safe, because each instance got a copy" is false: on 0.9.12 a frontend
  var's assigned list default was shared by every new session, and a backend var's `.default` assignment was ignored.
  Rewording in `verify_class_state5/NOTES.md`.

Optional, same area: **A5-03** — when a backend default cannot be deep-copied, name `Class.var` and suggest `ClassVar` in
the import-time error (a5 fails fast, which is better than 0.9.12's compile failure, but the message is a bare
`cannot pickle '_thread.lock' object`).

## Maintainer decisions
- A5-01: fix (recommended) or document the snapshot as a breaking change.
- #7360's deprecation warning says `deprecation_version="0.9.13"` inside 0.10 — right only if #7360 also ships in 0.9.13.
- A4-01 / A4-02 (substate `add_var` of an ancestor's dynamic var; auto-setter collision with the deprecated
  `state_auto_setters`) — still open on a5, message text improved by #7519; low, take into 0.10.0 or file.

## File as issues, fix after release
### reflex
- A4-01 / A4-02 if not taken (above).
- A4-03 — document `sync=True` LocalStorage as last-storage-writer-wins across tabs (writes within ~1 RTT).
- `rx.remove_local_storage` of a synced key syncs `null` into a `str` var in other tabs (computed vars then raise) —
  pre-existing on 0.9.12; not filed yet.
- An app package without `__init__.py` breaks every state update with a misleading "no dispatch function for
  substate(s)" error — pre-existing on 0.9.12; `reflex init` always creates the file.
- Unchanged: #7506, #7508 (A3-13), #7509 (A3-07), #7510 (A3-08), #7479 (A3-05), #7459 (N-006 rest).

### Downstream
- reflex-clerk 1.0.3 writes backend vars through its state class (now a TypeError; already broken on every 0.10 alpha) —
  tell its maintainers to use `ClassVar`, or list it in the 0.10 release notes.
- reflex-enterprise: A3-10 (enterprise#274), N-033 (enterprise#262), A3-09 (enterprise#275); enterprise#261 closable. The
  0.10.0 release notes should tell enterprise users to upgrade reflex-enterprise to 0.9.7a5+ together with reflex (N-025).

## Stable line
Unchanged: stock `pip install 'reflex[db]'` still resolves 0.9.12 without greenlet — Linear ENG-13207 (0.9.13 with #7466).
