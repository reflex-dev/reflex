# Pre-release findings: GitHub tracking audit (2026-11-11)

Scope: every finding of the 0.11.0a1 pass (FINDING-001 … -048, PKG-A, side items in RELEASE_PLAN.md), every past
finding still open / filed-open / unknown in `prerelease-testing/REGISTRY.md` (baseline 0.10.0, on `testing/prerelease`),
and the 0.10.1a1/a2 pass (`runs/2026-10-23-v0.10.1a1`, `runs/2026-10-26-v0.10.1a2`; that pass is not in the registry and
none of its "file after release" items had been filed).

Repos: `reflex` = reflex-dev/reflex, `rxe` = reflex-dev/reflex-enterprise. States checked on GitHub 2026-11-11.
"merged" = PR merged; "closed" = issue closed as completed unless noted.

Label `release-train`: existed in reflex; created in rxe (implicitly, by labelling rxe#290; verified with get_label).
Applied to 191 reflex items and 34 rxe items (list at the end).

## 1. Tracked

### 1a. Current pass (0.11.0a1)

| Finding | Tracker | State | Disposition |
|---|---|---|---|
| 001 repeated `@rx.event` crashes import | reflex#7807, reflex#7810 | merged | fixed |
| 002 rxe MCPPlugin prod startup without deploy_url | rxe#290 (rxe fix), reflex#7806 (changelog line) | merged | fixed; needs an rxe release with reflex 0.11.0 |
| 003 `refs is not defined` (rxe AG Grid, page code) | reflex#7806 (shim + `refs` internal), rxe#290 | merged | fixed |
| 004 unregistered DeclarativeBase drops every table | reflex#7797 | merged | fixed (auto-detect bases) |
| 005 kept env.py exceptions crash run/db | reflex#7809 | merged | fixed |
| 006 kept env.py writes empty revisions | reflex#7809 | merged | fixed |
| 007 pyright 3.11–3.13 loses bare-handler arg types (+ `rx.event.EventCallback[int]`) | reflex#7810 | merged | fixed |
| 008 rxe MCP consent redirect to backend in dev | rxe#290 | merged | fixed |
| 009 `reflex db migrate` exit 1 on fresh rxe app | reflex#7817 | merged | fixed for `reflex db *`; backend-only residual filed as reflex#7849 |
| 010 `await State.handler()` outside an event on empty token | reflex#7821 | merged | fixed |
| 011 JSON column typed `object` | reflex#7798 | merged | fixed; generic-TypedDict gap filed as reflex#7846 |
| 012 `default_factory` NOT NULL migration | reflex#7815 | merged | fixed |
| 013 same table in two metadatas, random winner | reflex#7830 | open (new) | filed |
| 014 admin-dashboard guide gaps | reflex#7816 | merged | fixed (docs) |
| 015 mistaken handler return values accepted | reflex#7821 (squash carried #7796), reflex#7796 | merged | fixed; streaming follow-up is reflex#7761 (open, not ours) |
| 016 `@staticmethod` above `@rx.event` | reflex#7807 / #7810 | merged | fixed |
| 017 second env.py replacement overwrites env.old | reflex#7809 | merged | fixed |
| 018 serializer silent blanks (hybrid_property, expired) | reflex#7831 | open (new) | filed |
| 019 merged metadata drops naming_convention | reflex#7830 | open (new) | filed (same fix area as 013) |
| 020 tables.md serializer example | reflex#7816 | merged | fixed (docs) |
| 021 rxe `use_single_port` dev proxy never mounts | rxe#294 | open (new) | filed |
| 022 prod CORS default breaks TLS-proxied / split | reflex#7799 | merged | fixed (+ docs, changelog correction on train) |
| 023 CORS rejection shown as "unreachable" | reflex#7799 | merged | backend warning fixed; frontend remainder ignored (see 3a) |
| 024 `rx.App()()` breaking entry | reflex#7816 | merged | fixed (changelog) |
| 025 lifespan skipped behind non-http-safe middleware | reflex#7832 | open (new) | filed |
| 026 case-duplicate routes accepted | reflex#7833 | open (new) | filed |
| 027 prod repeated Ctrl-C does not force exit | reflex#7834 | open (new) | filed |
| 028 deprecation frames in reflex_components_* | reflex#7811 | merged | fixed |
| 029 package.json format flips | reflex#7812 | merged | fixed |
| 030 forked workers share redis contender id | reflex#7795 | merged | fixed |
| 030/033 side note: lock hand-off "instaque" starvation | reflex#7805 (issue), reflex#7801 (closed unmerged) | open | tracked (owner deferred) |
| 031 cross-worker updates lost after Redis outage | reflex#7835 | open (new) | filed |
| 032 dead worker's socket record -> new token | reflex#6345 (existing, not a QA issue) | open | tracked by existing issue (its "backend crash/restart" variant); not labelled |
| 033 kill -9 of a worker stops the server | reflex#7803 | merged | fixed |
| 034 / 035 client_state hint, identifier collisions | reflex#7804 | merged | fixed |
| 036 optional set ops crash | reflex#7800 | merged | fixed; follow-ups reflex#7826, #7827 closed by #7800 |
| 037 / 038 backend-var str / extra factory calls | reflex#7818 | merged | fixed |
| 039 unkeyed foreach lifecycle payloads | reflex#7820 | merged | fixed (warning + docs) |
| 040 on_mount in cond in memo body | reflex#7836 | open (new) | filed |
| 041 foreach with item hooks in memo crashes page | reflex#7836 | open (new) | filed (same root cause as 040) |
| 042 / PKG-A sibling floors | reflex#7813 | merged | fixed |
| 044 failing upload handler truncates response | reflex#7808 | merged | fixed |
| 045 dev monitor blames user handlers for lazy imports | reflex#7802 | merged | fixed |
| 046 blocking-monitor noise for third-party handlers | reflex#7837 | open (new) | filed (third-party part); env-var traceback ignored |
| 047 auto_memoize warning not deduped | reflex#7814 | merged | fixed |
| 048 f-string id in foreach shares one ref | reflex#7838 | open (new) | filed |
| events_await low: bg task await — caught exception toasts; memory-manager CancelledError | reflex#7839 | open (new) | filed |
| events_await low: stacked-decorator deprecation names only first method | reflex#7840 | open (new) | filed |
| client_vars CV-5 / CV-6 set match order, set arg arrives as list | reflex#7841 | open (new) | filed |
| client_vars CV-8 `split()` UTF-16 | reflex#7842 | open (new) | filed |
| client_vars CV-10 remaining backend-var misuse paths | reflex#7843 | open (new) | filed |
| test isolation leak `REFLEX_MANAGED_LOGGING` | reflex#7844 | open (new) | filed (leak confirmed in-process) |
| flaky `test_redis_token_manager_lost_and_found` | reflex#7845 | open (new) | filed |
| Windows `supervise_output` lingering descendant | reflex#7819 | open | tracked (filed earlier this pass) |
| generic TypedDict key access (found on #7798) | reflex#7846 | open (new) | filed (reproduced on the checkout) |
| pyright rejects stacked `@rx.event(...)` | reflex#7847 | open (new) | filed |
| public ref helper instead of `Var._as_ref()` | reflex#7848 | open (new) | filed (enhancement) |
| 009 residual: backend-only start without .web, plugin libs unbundled | reflex#7849 | open (new) | filed |
| rxe `collect_page_info` relative URLs | rxe#292 | open (new) | filed |
| rxe `/.well-known/oauth-protected-resource/_reflex/mcp` returns HTML | rxe#293 | open (new) | filed |
| rxe VarData(position=) + console.* deprecations (also registry ENT-08) | rxe#295 | open (new) | filed |
| ENT-07 prod cookie sync 405 (re-verified still broken) | rxe#262 | open | tracked |
| Refuted / reclassified claims (17) | — | — | nothing needed |

### 1b. Past passes — registry items (status at 0.10.0 was filed-open / open / unknown)

| Registry ID | Tracker | State now | Note |
|---|---|---|---|
| HYD-03 | reflex#7484 | open | |
| HYD-04 / EVT-11 | reflex#7253 (PR #7436 open) | open | |
| HYD-05 | reflex#7486 | closed | fixed in 0.10.1 |
| HYD-06 | reflex#7487 | closed | re-verified fixed on 0.11 |
| HYD-07 (unknown) | reflex#6345 (existing) | open | reproducible on demand; = FINDING-032 |
| HYD-10 | reflex#7508 | closed | |
| HYD-13 | reflex#7506 | closed | re-verified fixed |
| HYD-16 | reflex#7247 | closed | fixed in 0.10.1 |
| STATE-08 | reflex#7263 | open | moot per registry (decision issue) |
| STATE-10 | reflex#7459, #7732 (closed, via #7651) | closed | remainder filed as reflex#7843 |
| STATE-21 | reflex#7491 | closed | re-verified: 3.11 vs 3.12 identical |
| STATE-22 | reflex#7498 | closed | residual int/list factories ignored (3a) |
| STATE-23 | reflex#7499 | closed | does not reproduce |
| STATE-24 | reflex#7488 | closed | |
| STATE-25 | reflex#7477 | closed | |
| STATE-26 | reflex#7483 | closed | re-verified fixed |
| STATE-34 | reflex#7264 | closed | |
| STATE-36 | reflex#7258 | closed | fixed in 0.10.1 (#7304) |
| EVT-01 (documented) | reflex#7239 | open | detached-events feature request |
| EVT-08 | reflex#7248 (PR #7412 merged) | closed | re-verified fixed |
| EVT-09 | reflex#7246 | closed | |
| EVT-10 | reflex#7251 | closed | |
| EVT-12 | reflex#7254 | closed | |
| EVT-14 | reflex#7478 | closed | |
| EVT-15 | reflex#7476 | **open** | re-verified FIXED on 0.11.0a1 (#7696); issue can be closed by a maintainer |
| EVT-16 / EVT-17 | reflex#6122 (comments) | open | EVT-16 re-verified fixed, EVT-17 changed on 0.11 |
| ENT-03 / ENT-04 | rxe#225 | open | fixed in rxe 0.9.7 per registry |
| ENT-09 | rxe#226 | open | |
| ENT-11 | rxe#227, rxe#267 | open | |
| ENT-12 | rxe#228 | open | fixed in rxe 0.9.6 per registry |
| ENT-13 | rxe#229 | open | |
| ENT-14 | rxe#230 | open | |
| ENT-15 | rxe#268 | open | still present on 0.11 (tickets demo) |
| ENT-23 (unknown) | rxe#250 (PR, open) | open | fix PR not by the campaign |
| ENT-26 | rxe#254 | open | |
| ENT-27 | rxe#245 (fix PR rxe#258 open) | open | |
| ENT-30 | rxe#261 | open | fixed in reflex 0.10.0; re-verified |
| ENT-31 … ENT-40 | rxe#269, #270, #271, #263, #264, #265, #266, #272, #275, #274 | all open | |
| ENT-08 | rxe#295 | open (new) | filed now (with the VarData deprecations) |
| PKG-04 | reflex#7088 | closed | R101-12 alpha-only variant, see 3c |
| CLI-09 | reflex#7266 | closed | fixed in 0.10.1 |
| CLI-11 | reflex#7092 | closed | |
| CLI-15 | reflex#7485 | closed | |
| CLI-17 | reflex#7245 | closed | |
| CLI-19 | reflex#7252 | open | |
| CLI-22 | reflex#5534, reflex#5394 (existing) | open | partly addressed by schema-mismatch detection (#7553/#7653) |
| CLI-24 | reflex#7479 | open | |
| CLI-25 | reflex#7480 | closed | |
| CLI-26 | reflex#7509 | closed | fixed in 0.10.1 |
| CLI-27 | reflex#7510 | closed | re-verified fixed |
| CLI-28 | reflex#7432 | closed | |
| CLI-34 (unknown) | reflex#6463 (existing, soft 404) | open | |
| CLI-36 (unknown) | reflex#7686 (existing) | closed | fixed |
| CMP-09 (unknown) | reflex#5780 (existing) | open | |
| CMP-13 | reflex#7098 | closed | |
| CMP-14 | reflex#7099 | open | unchanged on 0.10.1 |
| CMP-15 | reflex#7100 | closed | R101-19 remainder ignored |
| CMP-18 | reflex#7102 | open | |
| CMP-24 (unknown) | reflex#7792 (existing fix) | merged | re-verified fixed |
| CMP-27 (unknown) | #7564 / #7707 / #7691 | merged | re-verified fixed |
| CMP-28 | reflex#7426 (PR #7442 merged), reflex#7309 | #7426 closed, #7309 open | |
| CMP-29 | reflex#7430 | closed | |
| CMP-30 | reflex#7250 | closed | |
| CMP-32 | reflex#7255 | open | |
| CMP-34 | reflex#7244 | closed | re-verified fixed |
| CMP-35 | reflex#7262 | closed | re-verify on 0.11 still ~70 KB heavier with lazy libs |
| CMP-36 | reflex#7249 | closed | |
| CMP-40 | reflex#7429 | closed | fixed in 0.10.1 |
| CMP-41 | reflex#7431 | closed | |
| CMP-43 | reflex#7489 | closed | |
| CMP-47 | reflex#7852 | open (new) | filed now (never filed before) |
| CMP-50 | reflex#7481 | closed | `split()` gap filed as reflex#7842 |
| CMP-51 | reflex#7482 | closed | |
| DOC-04 | reflex#7260 | open | |
| DOC-05 | reflex#7261 | closed | |
| TP-01 | reflex-chat#61 | not checked (outside scope) | |
| TP-04 | reflex-examples#324 | not checked | no longer reproduces on 0.10.1 or 0.11 |

### 1c. Past pass — 0.10.1a1/a2 (not in the registry)

| Finding | Tracker | State | Note |
|---|---|---|---|
| R101-01 stale memo consumers after AG Grid edit | rxe#282 (contributor PR) | merged | AG Grid fixed; reflex-side guard ignored (3c) |
| R101-02 fork preload changelog | reflex#7646 | merged | |
| R101-04 sibling floors | reflex#7662 | merged | |
| R101-05 form change changelog | reflex#7646 | merged | |
| R101-07 rxe REST client_ip | rxe#279 | merged | |
| R101-08 React Compiler bail-outs | #7694 (existing) | merged | changed on 0.11: warning logged |
| R101-09 XFF token not validated | reflex#7854 | open (new) | filed now |
| R101-10 `reflex deploy` hides progress | reflex#7850 | open (new) | filed now |
| R101-11 export crashes on symlinks | reflex#7851 | open (new) | filed now |
| R101-13 `[None]` for empty id'd checkbox group | reflex#7540 (open PR: form data from names only) | open | obviated once id-based form fields are removed |
| R101-14 radio_cards as_child | reflex#7555 (existing) | closed | fixed |
| R101-15 non-str storage type errors | — | — | does not reproduce on 0.11 (STATE-23) |
| R101-19 moment unknown props | reflex#7100 | closed | remainder ignored |
| R101-22 recharts deep-freeze vs AG Grid edit | rxe#282 | merged | fixed as a side effect |

## 2. Filed now

reflex-dev/reflex (all labelled `release-train`):

| Issue | Finding | Summary |
|---|---|---|
| #7830 | 013 + 019 | Merged model metadata: duplicate table picked at random per process; base naming_convention dropped |
| #7831 | 018 | DeclarativeBase serializer: hybrid_property never sent, expired instances serialize as {} |
| #7832 | 025 | A middleware raising on a lifespan scope silently disables a FastAPI transformer's lifespan (INFO only) |
| #7833 | 026 | Routes differing only in case accepted silently; one page unreachable |
| #7834 | 027 | Prod `reflex run`: repeated Ctrl-C does not force exit during stuck lifespan cleanup |
| #7835 | 031 | Redis outage > ~5 s kills lost-and-found subscribers; cross-worker updates stop |
| #7836 | 040 + 041 | Hooks under rx.cond / rx.foreach inside an `@rx.memo` body are hoisted (cond fires unconditionally, foreach crashes) |
| #7837 | 046 | Dev blocking monitor: third-party handler warnings not actionable (enhancement) |
| #7838 | 048 | f-string id in rx.foreach gives every row the same ref; set_focus / set_value hit the last row |
| #7839 | events_await lows | Awaiting a handler from a background task: caught exception still toasts; memory manager CancelledError for a finished supersedes handler |
| #7840 | events_await low | "Decorators above `@rx.event`" deprecation names only the first method per class |
| #7841 | CV-5 / CV-6 | Set vars: rx.match compares order-dependent JSON; set[str] handler arg arrives as list |
| #7842 | CV-8 | StringVar.split() with empty separator splits UTF-16 code units |
| #7843 | CV-10 | Backend var as child / typed prop / event arg still cryptic; `State._x == ...` silently False |
| #7844 | test leak | In-process CLI invocation leaves REFLEX_MANAGED_LOGGING=true for later tests |
| #7845 | flaky test | test_redis_token_manager_lost_and_found intermittently fails after reconnect |
| #7846 | #7798 review | Key access on a parametrized generic TypedDict Var raises VarAttributeError |
| #7847 | #7807 note | pyright rejects `@rx.event(...)` stacked above `@rx.event` |
| #7848 | #7806 follow-up | Public API for a component ref Var instead of `Var._as_ref()` / raw `refs[...]` (enhancement) |
| #7849 | 009 residual | Backend-only start without .web serializes initial state with no plugin libraries bundled (rxe apps die) |
| #7850 | R101-10 | `reflex deploy` hides progress/success: export leaves console at WARNING |
| #7851 | R101-11 | `reflex export` crashes on outside-pointing or dangling symlinks |
| #7852 | CMP-47 | rx.data_editor with on_delete: Delete throws `reading 'length'`, cell not cleared |
| #7854 | R101-09 | trusted_proxy_hops: selected X-Forwarded-For entry used verbatim, no IP validation |

reflex-dev/reflex-enterprise (all labelled `release-train`):

| Issue | Finding | Summary |
|---|---|---|
| #292 | #290 follow-up | MCP server info / event API page list use relative URLs on reflex 0.11 without deploy_url |
| #293 | #290 follow-up | Advertised `/.well-known/oauth-protected-resource/_reflex/mcp` returns app HTML in single-port prod |
| #294 | 021 | `use_single_port=True` dev proxy never mounts (lifespan param named `app` gets the rx.App) |
| #295 | ENT-08 + VarData note | rxe triggers reflex deprecation warnings: VarData(position=), console.* shims |

## 3. Deliberately ignored

### 3a. Current pass

| Finding | Reason |
|---|---|
| 023 remainder (frontend "reachable but refused" toast, engine.io's own log line) | #7799 added the actionable backend warning; the browser WebSocket API does not expose the 403, so telling the cases apart needs an extra no-cors probe. Added complexity for a diagnostic that the backend log now covers. |
| 046 invalid `REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD` prints a traceback | Generic config-error path shared by every env var; the last line already names the variable and the rule. |
| 007 recommendation: CI pyright run with `--pythonversion 3.12` | CI-policy decision for maintainers, not a product defect; #7810 fixed the typing. |
| 011 / #7798 note: `Mapped[list[dict]]` over `ARRAY(JSON)` stays `List[object]` | Rare column type (Postgres ARRAY of JSON); `.to(...)` works around it. |
| #7797 note: `drop_column` on registered models not guarded | Intended alembic behaviour; #7797 already warns on dropped tables. |
| CV-4 per-row client state follows the index without `key` | #7820 now warns for unkeyed foreach items with lifecycle hooks and documents index keying; remaining docs nit only. |
| CV-9 storage-producing `default_factory` on int / list vars stays ordinary | Contrived declaration; the documented form `x: int = rx.LocalStorage("5")` works; extending the check costs another factory call (FINDING-038 tension). |
| #7807 note: `@staticmethod` above `@rx.event` on a non-state class returns an EventSpec | Calling such a method through the class is documented as unsupported in the #7673 changelog; nothing inspects non-state classes. |
| #7806 embed-mode `globalThis.refs` overwrite (two apps in one window) | Owner merged with the thread open, accepting current behaviour; compatibility global only. |
| #7800 CodSpeed cost of optional-array guard | Owner accepted the cost when merging. |
| #7795 residual SADD-in-flight cancel race | Bounded by the key's pexpire; no user-visible effect found. |
| 029 / 045 / 047 etc. | Fixed (see 1a). |

### 3b. Registry items (open / unknown, not filed)

| Registry ID | Reason |
|---|---|
| HYD-11 sync=True last-writer convergence | By design per verifier; docs nit only. |
| HYD-12 remove_local_storage syncs null | Re-verified fixed on 0.11.0a1. |
| HYD-14 (unknown) storage defaults after backend rehydrate | Never verified; the confirmed variant (R101-16) self-heals on reload; see 3c. |
| STATE-06, STATE-35, ENT-10, ENT-18, ENT-19, PKG-14, CLI-18, CMP-26, CMP-33, CMP-39 | Deliberately not filed in earlier passes by maintainer decision; nothing new. |
| STATE-27, STATE-28, STATE-29, STATE-31, STATE-32 | LOW error-message quality in rare class-definition patterns; not re-tested since 0.10.0. |
| STATE-33 large mutable defaults deep-copied | Consequence of the A5-01 design shipped as a documented breaking change; perf only. |
| STATE-37 (unknown) same-named ComponentState in two modules | Never triaged or reproduced since 0.9.11a1; needs a fresh repro before filing. |
| EVT-13 ty / pyright 5-arg typing | Changed on 0.11 (mypy OK, #7752 typed 5–8 args); ty is not a supported checker target. |
| ENT-06 (unknown), ENT-41 (unknown) | Never triaged; LOW; not re-tested. |
| PKG-07 otel upgrades reflex-base | Accepted as not practically fixable (2026-09-11). |
| PKG-10 unique UUID callable default backfill | Ignored at the user's direction (A1). |
| PKG-12 Bun installer edits shell profile | Upstream installer side effect. |
| PKG-15 rx.Model deprecation location in pydantic internals | Cosmetic; warning text names rx.Model; still present. |
| CLI-21 npm notice printed twice | Cosmetic. |
| CLI-30, CLI-33 (unknown) | Never triaged; not reproduced since 0.9.11a1. |
| CLI-37 reflex-otel swallowed SDK config error | Not re-verified since 0.9.11a2; the documented recipe was fixed (DOC-02). |
| CMP-23 Windows device names in frontend_path | Extreme edge case. |
| CMP-42 (unknown) Grid.js TypeErrors | Never reproduced. |
| CMP-44 React 19.3 extra console error | Only with reflex-clerk; upstream React behaviour. |
| CMP-45 DataEditor callback escapes foreach scope | Very likely fixed by #7792 (item hooks run inside the loop body; CMP-24 re-verified fixed); not re-run for data_editor. |
| CMP-46 DataEditor typing loses leading characters | Root cause unproven, likely upstream Glide lazy overlay timing; not re-verified. |
| CMP-48, CMP-49 DataEditor overlay / Radix synthetic clicks | LOW, likely upstream Glide; not re-verified. |
| TP-02, TP-03, TP-05 … TP-09 | Third-party packages / reflex-examples apps, outside reflex and reflex-enterprise. |
| DOC-03 duplicate changelog entries, DOC-08 wrong links | Historical changelog text; DOC-08 ignored at user's direction. |
| DOC-06 asession docs | Changed: documented in 0.11 database docs. |
| DOC-12 0.10 upgrade-guide sentence | Historical guide; low value now. |

### 3c. 0.10.1 pass items (not filed)

| Finding | Reason |
|---|---|
| R101-01 general reflex-side guard against components mutating store objects | AG Grid (the common case) fixed in rxe#282; a generic guard in structural sharing costs on every delta; no other mutating component reported. |
| R101-03 sdist hook deps unpinned (stubs lost when building alpha sdists) | Only affects users building alpha sdists from source; wheels ship stubs and CI sets PYI_GENERATOR_RAISE_FAILED_IMPORTS; packaging-policy decision. |
| R101-06 malformed `__reflex_form_data__` envelope | Browsers never send it; only hand-crafted socket messages or a control named with the reserved key. |
| R101-12 uv cannot build the alpha sdist | Alpha-only; finals carry no pre-release specifiers; `-b build-constraints.txt` workaround. |
| R101-16 storage vars at defaults after bg-task rehydration | Pre-existing end state; self-heals on reload; not re-verified on 0.11. |
| R101-17 one "never awaited" wrapper warning | Trivial; only for filters that do not `.close()` the withheld coroutine. |
| R101-18 stale postcss.config.js after removing TailwindV4Plugin | Rare action; deleting `.web` fixes it. |
| R101-19 moment provider `format` vs child `from_now` | LOW, component-specific; unknown-props part closed in #7100. |
| R101-20 typing gaps (ty) | ty is not a supported checker target; pyright/mypy clean. |
| R101-21 rxe MCP consent race on Redis | Intermittent, no minimal repro recorded. |

## Not resolved / for the release owner

- reflex#7476 (EVT-15) is still open although the 0.11.0a1 pass re-verified it fixed; reflex#6122 likewise (EVT-16 fixed, EVT-17 changed). Not closed (not ours to close).
- reflex#7262 (CMP-35) is closed, but the 0.11 re-verify still measures ~70 KB extra JS with lazy libraries.
- #7821 review note "StateProxy partial in background tasks = documented gap, follow-up": no concrete repro recorded; not filed.
- reflex-chat#61 (TP-01) and reflex-examples#324 (TP-04) states were not checked (other repositories).
- rxe#282 (R101-01 fix) and the A1-era rxe fix PRs (#242, #243, #246, #250, #255, #256, #258) and contributor fix PRs in reflex were not labelled: they were not opened by a campaign. Add the label if you consider them part of the train.

## Items labelled `release-train`

reflex issues: 6972–6983, 7088–7104, 7211–7214, 7235, 7244–7266, 7429–7432, 7459, 7468–7491, 7498, 7499, 7506–7511,
7805, 7819, 7826, 7827, 7830–7852, 7854.
reflex PRs: 6971, 6984–6987, 6989–6992, 6994, 7085–7087, 7105–7110, 7215–7218, 7456, 7460–7462, 7465, 7466, 7492–7497,
7505, 7512–7514, 7516, 7519, 7523, 7646, 7662, 7795–7804 (incl. 7801), 7806–7818, 7820, 7821.
rxe issues: 225–230, 245, 252–254, 260–272, 274, 275, 292–295. rxe PRs: 232, 235, 273, 279, 290.
