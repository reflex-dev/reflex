# Runtime PR survey, reflex v0.10.1..v0.11.0a1
Source: git log/show on v0.11.0a1 commits (squash messages, stats, hunks); GitHub PR API not used (commit bodies carry the PR text). Titles = commit subjects.
"Untested" lists = my inference from the PR's file list (not from reading every test); verify before reporting as a bug.

## Cross-cutting flags (read first)
1. #7673/#7770: changelog (root + reflex-base CHANGELOG.md in v0.11.0a1) ALREADY reflects the revert (see #7770 section). No stale "stateless" text found by grep.
2. #7624: `rx.App().__call__` now returns `_RootMiddleware` (plain ASGI callable), not Starlette. Documented only in a *performance* fragment. Anything doing `app().routes`, `.add_middleware`, `.mount`, `.state`, `.router` on the result breaks (enterprise? sentry/otel wrappers? test clients that use app()). Also `starlette_app` lifespan-task arg semantic changed.
3. #7641: prod default CORS changed from ["*"] to "no CORS middleware" when deploy_url unset; deploy_url default None (was http://localhost:3000); frontend_port no longer derives it. Breaks split-origin prod (static frontend host + separate api_url), cross-origin rx.upload / REST API calls from browsers, third-party embeds.
4. #7650: `reflex_base.utils.log.supervise_output`/`is_output_supervised` removed (moved to new `reflex_base.utils.supervisor`). Internal-ish but importable; check reflex-enterprise / hosting-cli for imports of `reflex_base.utils.log` supervisor symbols.
5. #7757: socket_timeout=None applied to ALL Python versions and all redis clients (commit text says "3.11" but code in `_redis_client_kwargs` is unconditional): half-open Redis TCP connections never time out (same as redis-py 7). redis cap widened to <9.
6. #7673 breaking: `@rx.event` now returns EventHandler (not function); decorator stacked above @rx.event deprecated; decorated non-state class methods warn.
7. #7615-ish deprecation_version in #7770 is "0.10.2" although this is 0.11.0a1 (minor: warning text/version metadata inconsistent).

---------------------------------------------------------------------
## #7673 Make event handlers awaitable and register them through @rx.event
Intent: `await State.handler(args)` inside a handler runs it inline on the locked state and returns its value; `@rx.event` returns the EventHandler itself (bound via __set_name__ at class creation); handler return values resolve EventFutures instead of TypeError.
Runtime: reflex_base/event/__init__.py (+296; EventHandler/EventSpec __await__), event/context.py (lock bookkeeping on EventContext), processor/base_state_processor.py (+346; inline executor, enqueue-and-await when no lock held), event_processor.py, reflex/state.py (+66), istate/proxy.py, app.py, vars/base.py (literal var proxy cache fix: TypeError when proxied dict then other proxied kind passed to handler).
Tests: huge unit set (test_base_state_processor.py +1464 lines, test_state.py +214, test_event.py +92, test_context, test_proxy, test_app, test_base vars) + integration test_background_task.py (+46) and test_event_chain.py (+28).
Untested/try:
 - `await Other.handler()` from a background task (`async with self`) vs without lock held ("enqueued and awaited" path) under Redis state manager with lock_expiration short; deadlock if awaited handler waits for the same token's lock (enqueue path while a foreground holds it).
 - Awaiting a handler that is itself a generator/async-generator, raises, or is cancelled (client disconnect / supersedes=True) mid-await; does parent get exception? state lock released?
 - Await handler inside `async with self` that takes get_state() of a substate / linked state (#7738 interplay); await of handler defined on a different substate; await in on_load chain.
 - Awaiting handler with throttle/debounce/stop_propagation event_actions; handler returning a coroutine (documented "still raises"); handler returning rx.event spec chain then awaited value.
 - Decorator order: `@other_decorator @rx.event def ...` (now deprecated) and `@rx.event` on staticmethod/classmethod/plain-class method (warn); `@rx.event` handlers inherited by mixin classes / subclassed states (binding at __set_name__ vs old registration) ; dynamic setvar/auto setters; `self.handler()` still plain call.
 - Public-API change flags: `@rx.event` return type (EventHandler vs function): code that introspects `fn.__wrapped__`, calls decorated method as a plain function from non-state code, pickling/dill of states containing handlers; EventHandler is now awaitable (`inspect.isawaitable`-based checks in user code/other libs may change).
Floor bump: reflex-base>=0.10.2.dev0 (EventContext lock methods) -> check reflex pin vs published reflex-base alpha.

## #7770 Revert stateless event handlers from #7673  (PRECISE)
Reverted: ONLY the "stateless handler" feature = a module-level function decorated with @rx.event whose first param is NOT a BaseState subclass, which #7673 registered via RegistrationContext.register_event_handler and ran WITHOUT the state lock / outside per-token FIFO / before middleware (auth bypass for reflex-enterprise AuthMiddleware). Now: such a function is left as the plain function, `console.deprecate("@rx.event on a function without a state parameter", deprecation_version="0.10.2", removal_version="1.0")`, returns func, registers nothing (incl. generic-annotated first param). Removed: EventDecorator/EventNamespace stateless overloads, base_state_processor stateless run path (-55), event_processor (-14), docs/events/decentralized_event_handlers.md "Stateless Event Handlers" section, 266 test lines.
KEPT from #7673: awaitable handlers, return values resolving futures, `@rx.event` returning EventHandler, decorator-order deprecation.
Changelog check (v0.11.0a1 CHANGELOG.md line 13 breaking fragment and line 25 feature fragment, both root and reflex-base): breaking text now says "A module-level function decorated with @rx.event whose first parameter is not a state stays a plain function and warns; drop the decorator"; feature text no longer mentions stateless. => changelog does NOT describe the reverted behaviour. (The fragments were edited in the revert commit, both copies.) Residual: deprecation_version "0.10.2" is stale; the breaking entry is under #7673 link, not #7770.
Tests: test_event.py (+52/-?) asserts decorator warns, returns original function, registers nothing; test_state.py adjusted.
Untested/try: existing user code that used stateless `@rx.event async def f(x: int)` in 0.10.2-dev builds (never released in a stable? 0.10.1 is stable, so only dev users); function whose first param is annotated with a string/forward ref or Optional[State] or a Mixin (not BaseState subclass) -> now deprecated plain func instead of handler: check decentralized handlers with `state: "MyState"` string annotations and Protocol/mixin states; get_type_hints failure on unresolved forward refs.

## #7782 fix: run middleware preprocess on awaited event handlers
Intent: an awaited handler must go through app middleware (auth gate) like a queued one.
Runtime: middleware carried on EventContext (context.py +5, event_processor +2); base_state_processor shares one `_process_middleware` step for queued + inline paths; blocked awaited handler doesn't run, its update reaches client, await returns None; streaming context (upload handlers via enqueue_stream_delta) copies middleware; preprocess runs inside registered inline run so lock isn't released by detached child.
Tests: test_base_state_processor.py +182 (wired_app fixture), docs chaining_events.md.
Untested/try: reflex-enterprise AuthMiddleware + `await Protected.handler()` from public handler (confirm blocked, and what the caller sees: None, not exception); rx.upload handler with middleware that blocks (now gated: behaviour change for upload); middleware that mutates event/ returns update; middleware raising; async middleware slow + redis lock expiration; awaited handler from background task.
Flag: behaviour change for uploads (now middleware-gated) not in a changelog entry I saw (only +inline-await-middleware bugfix).

## #7715 fix(event): type rx.event handlers as EventCallback under mypy
Intent: mypy users can call @rx.event handlers; `rx.event.EventSpec` valid annotation. Runtime: none (TypeAlias annotations on EventNamespace re-exports in event/__init__.py). Tests: none runtime (type-only). Try: run mypy+pyright on app with `@rx.event` handlers, `rx.event.EventCallback[int]` annotations; check no runtime import cycle. Low risk.

## #7752 Type event handler calls with five to eight positional values
Intent: type-checkers accept handlers with 5-8+ args. Runtime: none (overloads in event/__init__.py). Tests: tests/type_checking/event.py. Untested: keyword args stay untyped; ty/pyright/mypy matrix on handlers with 9+ args, *args, defaults. Low risk.

## #7755 Overload EventHandler.__get__ so a stored handler reads as itself
Runtime: none (typing overloads). Tests: type_checking/event.py. Try: dataclass field typed EventHandler, rx.memo EventHandler param, pyright strict. Low risk.

## #7754 Type FunctionStringVar.create with an EventChain var type
Runtime: none (overload in vars/function.py). Tests: type_checking/vars.py. Low risk.

## #7696 fix(event): send a failed handler's writes after its last yield
Intent: writes after last yield of a handler that raises/is cancelled reach the frontend (matters for redis, which reloads fresh copy and drops dirty marks).
Runtime: base_state_processor flushes delta under state lock before exception propagates; flush failure logged; flush only if a write is pending. docs yield_events.md.
Tests: test_base_state_processor.py +201 (unit only; no integration/redis end-to-end).
Untested/try: real Redis (not mock) + handler `self.x=1; raise` -> UI shows x=1 plus error toast ordering; cancel via client navigation (supersedes) mid-handler; handler raising after a yield with computed vars/cached vars dependent on written var (flush recomputes); backend_exception_handler also returns an update (double delta); background-task handlers (not covered: "foreground handler" only).
Possible undocumented change: partial writes before an exception are now visible in UI where previously (memory) they appeared with next delta; apps relying on exception = "nothing shown" see differences. Docs updated (yield_events.md).

## #7412 fix(state): persist cancelled redis handler updates
Intent: with redis state manager a cancelled/raising handler's state writes are saved (matches memory/disk).
Runtime: reflex/istate/manager/redis.py (+47): save on any handler exception (non-cached paths) and through repeated cancellation. Docs: write after last yield reaches frontend only with a later update on Redis (note interplay with #7696 which later flushes; docs line may be stale/contradictory after #7696 - check docs/events/yield_events.md wording).
Tests: test_redis.py +176 (mock redis), test_base_state_processor +73.
Untested/try: real redis, client disconnect mid-handler, two tabs same token... ; handler raising halfway through multi-field update leaves partially-applied state persisted (behaviour change vs rollback expectation); redis oplock/lease mode (#7534) + cancel.

## #7534 fix(state-manager): stop redis lock handoffs from stalling events until the lock expires
Intent: no multi-second stalls when two events/tabs/processes contend for the same token under redis.
Runtime: istate/manager/redis.py rewritten substantially (+583/-): lock release on cancelled/late handoffs, lease lock renewal only while owned and within use's lock_expiration, remote waiters re-register, `_Lease` dataclass, renewal timer instead of asyncio.wait_for (3.11 cancel-swallow), flush-cancel keeps lock until write lands, failed lease reported once.
Tests: test_redis.py +858 and mock_redis.py +43 (mock only; no real redis integration in diff).
Untested/try: real redis, >=2 backend workers (granian multiple workers) hammering same token (rapid clicks + background task); lock_expiration shorter than a slow handler; redis restart/failover mid-lease; Python 3.11 vs 3.12 vs 3.14; many tokens (perf/regression: lease bookkeeping, memory); redis cluster/sentinel; upload + background task concurrency.
Risk: largest hand-rolled concurrency change; highest chance of deadlock/regression. Mock redis may diverge from real semantics (pubsub timing).

## #7751 Start the redis lock subscriber on the loop that serves the app
Runtime: removes eager lock-task start in StateManagerRedis.__post_init__ (3 lines); task starts lazily on first use. Tests: test_redis.py +20, test_state.py +5.
Untested/try: first request latency / first modify_state before subscription confirmed (lease not taken -> behaviour = slower path?); app built in one loop, served in another (AppHarness, uvicorn --reload, granian); close() when subscriber never started; hot reload with redis.

## #7757 Allow redis-py 8; drop its socket timeout to fix the Python 3.11 cancellation hang
Runtime: pyproject redis bound <9; prerequisites.py `_redis_client_kwargs()` -> retry_on_error+socket_timeout=None for ALL clients (async, pool, sync) on ALL Python versions (despite commit text "on 3.11"); redis.py narrows bytes|str replies.
Tests: test_prerequisites.py +51 (kwargs asserted), test_redis, token_manager tests.
Untested/try: redis-py 8 real server on 3.10/3.12/3.13/3.14 (RESP3 default behaviours: pubsub message shapes, MGET types); redis blackhole (iptables drop) -> commands now hang forever (no socket timeout) -> handlers/shutdown hang; user-supplied REFLEX_REDIS_URL query params (socket_timeout=...) vs kwargs precedence; rediss/TLS, sentinel URLs; reflex-enterprise own redis clients unaffected? Downstream: enterprise token manager creating its own clients.
Flag: undocumented broad behaviour change (timeouts removed everywhere).

## #7738 fix: a background task cancelled while entering a state from get_state no longer leaves the client's state locked
Runtime: istate/proxy.py (+13): linked-state proxy __aenter__ exits parent context when loading the linked state fails/cancelled. Tests: test_proxy.py +75 (memory?). 
Try: `async with self` then `async with await self.get_state(Other)` cancelled by client disconnect/reload while get_state loads under redis; state load raising (unpickle error) -> next event proceeds?; nested get_state of 3 levels; combine with awaitable handlers.

## #7616 fix: recompute cached vars after a hot reload
Runtime: istate/manager/__init__.py (+30 `_drop_cached_var_values`), disk.py (+10), redis.py (+38 tracks states written this process); only under dev env + dev backend reloader. Fields kept.
Tests: test_disk.py +87, test_redis.py +147 (unit).
Untested/try: real `reflex run` hot reload edit of a @rx.var(cache=True) getter with disk and redis, state with backend-only vars, nested substates, cached var depending on other cached var / external data (recompute cost: expensive getters re-run after every reload); preview/prod (should be unchanged); `reflex run --env prod` backend started separately.

## #7590 fix(config): honor state_auto_setters when the app imports before the config
Runtime: reflex/utils/exec.py (+23) new worker target `reflex.utils.exec:_backend_app` factory: loads config, then imports app and builds ASGI app; ALL server paths (granian/uvicorn/gunicorn) now use it. Earlier get_state_auto_setters change dropped.
Tests: test_exec.py +45, test_granian_module_target.py updated.
Untested/try: ALL backend start modes: dev (reload on/off), prod granian single/multi-worker, uvicorn/gunicorn (REFLEX_BACKEND_ASGI?), custom `app_module_import`, spawn vs fork (REFLEX_BACKEND_START_METHOD), Windows; external server runs `granian reflex_app:app` / `uvicorn app.app:app` (not via factory) -> auto setters still missing?; Dockerfile/Procfile/Helm docs referencing target `app.app:app.api` strings; reflex-enterprise or hosting deploy templates that hard-code the granian target string; app whose import raises.
Flag: possible downstream break if anything parses the old target string.

## #7672 feat: detect event loop blocking in development
Runtime: new reflex_base/event/processor/blocking.py (EventLoopBlockingMonitor thread; samples loop thread frames; warns when threshold reached, logs total after); config `event_loop_blocking_threshold` (default 0.2s, 0 disables, validated non-negative finite); enabled only if threshold>0 AND REFLEX_ENV_MODE==DEV; env REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD; event task name prefix constant. Docs added in configuration.md; features fragment.
Tests: test_blocking.py +230, test_event_processor +119, test_app +13, test_config +36.
Untested/try: sync `time.sleep` handler, sync CPU-heavy computed var, sync DB (sqlalchemy) call, numpy/C-extension blocking; many concurrent events (monitor overhead); log noise at startup (compile/import blocking, first-request lazy imports); hot reload start/stop leak of monitor thread; REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD=abc / "0" / "-1" error messages; prod mode (should be silent); granian multi-worker.
New public config field -> check docs/api-reference/config updated (docs only mention configuration.md).

## #7746 test: make the blocking-monitor and orphaned-shutdown tests robust to slow runners
Test-only plus one small runtime fix in blocking.py (+6/-): report total whenever loop responded, even if stop() raced a timed-out probe. Tests: test_blocking.py, test_reflex.py. Low risk. Try: stop during block (hot-reload kill) -> total still logged once.

## #7653 feat: let the app handle a state schema mismatch
Intent: prod pages dispatch cancelable `reflex:state-mismatch` window event (detail {frontend, backend} hashes) before reload/banner; preventDefault skips both.
Runtime: template web/utils/state.js (+19/-?); always console.warn first on prod mismatch; dev unchanged (warn only, no event).
Tests: Playwright test_client_error.py (+161 refactor), JS test client_state_updates.mjs (+56). Docs exception_handlers.md.
Untested/try: real prod deploy rolling update with open tab (old tab, new backend); listener with preventDefault then later reconnect loop (socket reconnect storm? state sync broken until reload); multiple tabs; no listener = old behaviour (reload loop guard?); event dispatched under SSR/static export.
New public frontend API (event name + detail shape) -> must be supported long-term.

## #7621 fix: drain oversized polling POST bodies so a rejected connection event cannot stall the page
Runtime: reflex/app.py `_DrainOversizedBodyMiddleware(app, eio)` reads Content-Length vs engineio max_http_buffer_size, drains body, answers 400 itself and `socket.close(wait=False)`; wired into the engine.io mount; transport="polling" only.
Tests: test_app.py +252 (handshake, no-parked-poll regression w/ wait_for, mounted via App).
Untested/try: real browser with `transport="polling"` and oversized event (large rx.upload-less payload, big form value/hydrate), behind nginx/proxy with buffering; chunked (no Content-Length) bodies; websocket transport unaffected? ; REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE tiny value; reconnection afterwards; interplay with #7624 root middleware order (drain middleware vs CORS wrapper).

## #7522 Fix stale on_load during websocket connection
Runtime: template state.js (+27) and compiler templates.py (+3): hydration (auth) event uses the browser's current route at connect time; with navigation during the handshake only the LAST queued on_load_internal is kept (storage updates of each nav still sent).
Tests: Playwright test_navigation_before_connect.py (+87), JS state_js.test.mjs (+188), test_compiler.py (+6).
Untested/try: slow websocket (throttled network) + rapid link clicks across pages with on_load that redirect or set state; on_load with background task; cookies/localStorage-backed vars changing between navs; dynamic routes /[id]; hash/query-only navigation; reconnect after backend restart (not first connect); polling transport; 404 route during handshake.
Behaviour change: on_load of intermediate pages visited during handshake no longer runs (undocumented?) -> only news bugfix fragment (+7487).

## #7599 fix(route): match page routes case-insensitively like React Router
Runtime: reflex/route.py (+4/-?): route regex compiled with ASCII-only case folding. Tests: test_route.py +21 (incl. unicode non-folding).
Untested/try: `/About` vs `/about` both registered as distinct pages (collision? first wins?); dynamic args `/User/[id]` capture case preserved?; `router.page.path`, `router.page.raw_path` value for mixed-case URL; on_load firing for mixed-case URL; static prod server returns 200 for `/About` (static file lookups on case-sensitive FS = Linux!) vs frontend React Router; sitemap duplicates; catch-all `[[...splat]]`; 404 page with mixed case.
Possible undocumented behaviour change: duplicate-route detection (add_page of `/Foo` and `/foo`) not obviously handled.

## #7650 Give reflex run one owner for shutdown
Runtime: new reflex_base/utils/process_tree.py (stop_process_tree: /proc, ps, taskkill /T; one deadline then kill) and utils/supervisor.py (supervise_output moved out of utils/log.py, which loses is_output_supervised/_OutputPump/supervise_output); reflex/reflex.py `_run_dev` idempotent SIGINT/SIGTERM handlers (first unwinds into cleanup, repeats ignored, later Ctrl-C forces), exec.py, processes.py. `--json` supervisor: forwards every signal, 15s kill deadline, 30s drain wall, record-by-record write.
Tests: test_process_tree.py 237, test_supervisor.py 641, test_reflex.py +229, integration test_run_shutdown.py (+341: group SIGINT / pid SIGINT / pid SIGTERM x plain/--json/npm).
Untested/try: Windows & macOS real runs; `reflex run` under Docker/PID1/tini, systemd stop, supervisord, VS Code debugger, Jupyter/subprocess parent; `reflex run --backend-only` / --frontend-only / --single-port; backend with long lifespan shutdown task (is it given time before kill? 15s cap) ; reflex-enterprise or hosting-cli invoking `reflex run` with --json; hot-reload still works (signal handlers vs granian reloader); ps missing on slim images (fallback?). Removed names in reflex_base.utils.log = downstream import risk.

## #7693 Take config ports only for the side that reflex run starts
Runtime: reflex/reflex.py (+9/-2): config ports used only for the side being run. Tests: test_reflex.py +94 (unit). Try: `--frontend-only` with rxconfig backend_port set (no exit now) and `--backend-only` with frontend_port; `--frontend-port` with `--backend-only` still errors (documented?); env REFLEX_FRONTEND_PORT; port-in-use auto-increment unchanged; `reflex run --env prod --single-port`.

## #7624 Send ASGI lifespan events to api_transformer apps; drop the extra top-level Starlette app
Intent: FastAPI/Starlette api_transformer `lifespan` (on_startup/on_shutdown, yielded state on request.state) now runs; fewer layers/perf.
Runtime: app.py: `_ContextMiddleware`->`_RootMiddleware` (sets contexts; answers lifespan scope itself via `_serve_lifespan`, replaces Starlette(lifespan=...) wrapper, route-less); CORSMiddleware added on top only for the outermost (callable transformer) case; lifespan events sent to outermost app + each Starlette-transformer-mounted app (not user-mounted apps); order: Reflex lifespan tasks start first, transformers' lifespans next, stop in reverse; yielded state merged into ASGI lifespan state; app that raises/returns/does not support lifespan is skipped (logs "appears not to support"); warns when same lifespan also registered via register_lifespan_task (would run twice); app_mixins/lifespan.py (+102 `_run_lifespan`).
Tests: tests/units/app_mixins/test_lifespan.py +138, test_app.py +254, integration test_lifespan.py (19 lines changed).
Untested/try: 
 - FastAPI transformer with `lifespan` that opens DB pool/httpx client + reflex-enterprise REST API / enterprise plugins that register their own lifespan tasks (ordering, double-start); transformer list [fastapi_app, callable middleware, second FastAPI] mixing.
 - Callable transformer that does NOT forward lifespan (common: pure ASGI middleware that only handles http) -> skipped with log; transformer that raises on `scope["path"]` KeyError for lifespan scope (docs changed example from scope["path"] to .get) -> existing user middleware doing scope["path"] now CRASHES at startup (breaking!).
 - Starlette transformer that already has its own lifespan AND user registers it via register_lifespan_task (double-run warning vs actual); `starlette_app` lifespan-task arg semantics changed (now Reflex's inner Starlette).
 - Sentry/otel ASGI middleware (otel.asgi_middleware wraps top app; sentry Starlette integration #7139 `__call__ read-only` fix), granian vs uvicorn lifespan "auto/on" mode, hot reload shutdown (CancelledError lifespan_cleanup #7392), startup failure behaviour (lifespan.startup.failed; server exit code), uvicorn `--lifespan off`.
 - Static-frontend mount (REFLEX_MOUNT_FRONTEND_COMPILED_APP) + transformer; 500 responses get CORS headers (comment says covered by root CORS); rx.upload / /_upload with transformer; websocket scope still passes through root middleware.
 - Anything calling `app()` expecting Starlette (breaking; fragment is in "performance").
Flags: removal of top-level Starlette (no .routes/.state/.add_route on rx.App()() result), CORS now added in different places (double CORS headers if transformer also adds its own?), scope["path"] assumption in user middleware.

## #7641 fix(app): restrict default CORS origins to deploy_url in prod mode
Runtime: app.py `_cors_options`/resolver shared by Starlette CORS and Socket.IO; reflex_base/config.py: deploy_url default None (not derived from frontend_port), new `Config.frontend_url` property (deploy_url or http://localhost:<frontend_port>), sitemap plugin uses frontend_url; deploy_url normalized to browser-style origin (lowercase host, default port stripped); explicit cors_allowed_origins (rxconfig or env) used as-is; dev keeps "*". Prod with deploy_url unset => no CORS middleware, Socket.IO same-origin only.
Tests: test_app.py +171 (HTTP + Socket.IO origin enforcement), test_config +28, test_sitemap +63.
Untested/try:
 - Prod, frontend on separate origin (Vercel/S3/CDN, `reflex export --frontend-only`) with only api_url set -> websocket/HTTP now rejected unless cors_allowed_origins/deploy_url set (check message/logs clarity).
 - Prod behind reverse proxy rewriting Host/Origin, https termination (Origin https vs backend sees http), www vs apex, custom port, trailing slash/path in deploy_url, IDN host.
 - reflex-enterprise REST API / custom api_transformer FastAPI endpoints called from other sites/mobile apps/browser extensions; `rx.upload` / `/_upload` from cross-origin; `rx.download`/ fetch of backend URLs from embedded iframe; credentials=True with explicit list.
 - `reflex run --env prod` locally (frontend 3000, backend 8000 = cross-origin!) when not single-port: does default now break local prod runs? (docs say prod serves frontend from backend origin - verify with REFLEX_MOUNT_FRONTEND_COMPILED_APP unset).
 - Docker/Helm with env REFLEX_DEPLOY_URL; Codespaces/Gitpod where api_url overridden; sitemap link when deploy_url unset ("http://localhost:3000" in sitemap, same as before only by accident).
 - Anything reading config.deploy_url expecting a non-None string (enterprise, hosting-cli, user rxconfig) -> None now. Breaking public config default change (documented as breaking in both fragments).
