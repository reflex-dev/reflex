# reflex (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Breaking Changes

- Remove the `reflex component` CLI (`init`, `build`, `share`, `install`) and the `CustomComponents` constants. Wrap React libraries directly in your app as described in the wrapping React docs, and start reusable component packages from the [component template](https://github.com/reflex-dev/component-template), which builds, tests, and publishes them with standard Python tooling. ([#6425](https://github.com/reflex-dev/reflex/issues/6425))
- A substate may now declare a var or computed var with the same name as an inherited var: it gets an independent one of its own, instead of raising `BaseVarShadowsInheritedVarError` or `ComputedVarShadowsBaseVarsError`. A dynamic route arg only conflicts with a var of the state it is installed on. Assigning an undeclared state attribute still raises `SetUndefinedStateVarError` outside of prod mode, but no longer in prod. The internal class maps `backend_vars`, `inherited_vars` and `inherited_backend_vars`, `get_skip_vars()` and the instance `_backend_vars` are removed: use `get_fields()`, whose fields know the state they belong to. States saved by this release still load in workers of the previous one, so rolling deploys sharing Redis keep working, with one exception: while old workers remain, an in-place change to a mutable backend var (like `self._items.append(x)`) made on an old worker to a state saved by this release is not persisted. Assigning backend vars, and any change to frontend vars, is unaffected. ([#7312](https://github.com/reflex-dev/reflex/issues/7312))

### Features

- The duration settings read by the app and the state managers take a unit suffix: `SQLALCHEMY_POOL_TIMEOUT`, `REFLEX_SOCKET_INTERVAL` and `REFLEX_SOCKET_TIMEOUT` accept values such as `2m`, and `REFLEX_AUTO_RELOAD_COOLDOWN`, `REFLEX_OPLOCK_HOLD_TIME` and `REFLEX_STATE_MANAGER_DISK_DEBOUNCE` replace the `_MS`/`_SECONDS` names, which still work with a deprecation warning until 1.0. A bare number is read as seconds. ([#7138](https://github.com/reflex-dev/reflex/issues/7138))
- Set `REFLEX_REDIS_MAX_CONNECTIONS` to cap each Redis client's connection pool (the state manager, the token manager and the health check each use their own client). Once a pool reaches the cap, requests wait up to `REFLEX_REDIS_POOL_TIMEOUT` (default 2s, which must be above 0 and below the configured state-lock lifetime) for a free connection instead of opening new ones. ([#7179](https://github.com/reflex-dev/reflex/issues/7179))

### Bug Fixes

- Fixed `reflex db makemigrations`/`migrate` crashing with `CompileError` when autogenerating a migration that adds a column with a callable default (e.g. `default_factory=datetime.now` or `default=uuid.uuid4`) to an existing table; callable defaults are now evaluated before being carried as a SQL `server_default`. ([#6706](https://github.com/reflex-dev/reflex/issues/6706))
- Serve valid dynamic-route URLs (e.g. `/articles/7`) with HTTP 200 instead of 404 when loaded directly in self-hosted prod static serving, reserving 404 for genuinely unknown paths. ([#6996](https://github.com/reflex-dev/reflex/issues/6996))
- When a project keeps using npm because `reflex.lock/` only has `package-lock.json` (for example after a run with `REFLEX_USE_NPM=1`), Reflex now logs why and how to switch back to bun with `REFLEX_USE_NPM=0`. ([#7093](https://github.com/reflex-dev/reflex/issues/7093))
- Reflex now checks the Node.js version before running npm, so an unsupported Node.js no longer leaves npm lockfiles behind that switch later runs to npm. ([#7210](https://github.com/reflex-dev/reflex/issues/7210))
- Preserve ID-based form controls through automatic memoization while excluding IDs on non-controls from submissions. ([#7227](https://github.com/reflex-dev/reflex/issues/7227))
- Avoid reinstalling frontend packages on every compile or hot reload when bun or npm only changes the formatting of `package.json`. ([#7236](https://github.com/reflex-dev/reflex/issues/7236))
- `reflex db` commands run without the `db` extra installed now exit with the "pip install reflex[db]" message instead of a raw traceback. ([#7259](https://github.com/reflex-dev/reflex/issues/7259))
- Fix `TypeError: refs._client_state_set... is not a function` when a component sets a global `rx._x.client_state` value before any component reading `.value` has mounted, such as when the reader sits behind an `rx.cond`. ([#7286](https://github.com/reflex-dev/reflex/issues/7286))
- An editable install (`uv sync`, `pip install -e .`) no longer overwrites `.pyi` stubs that the checkout already has. A checkout missing any of them still gets them generated. ([#7303](https://github.com/reflex-dev/reflex/issues/7303))
- In a background task on a substate, in-place changes to a mutable var inherited from a parent state (like `self.items.append(...)`) are now sent to the client and persisted. ([#7312](https://github.com/reflex-dev/reflex/issues/7312))
- Fix stylesheet edits in `assets/` not applying in dev mode until a manual reload. The global stylesheet `<link rel="preload">` is now emitted only in production builds, so Vite's CSS hot update swaps the real stylesheet link again. ([#7317](https://github.com/reflex-dev/reflex/issues/7317))
- The memory and disk state managers now free expired session states right away instead of waiting for a garbage collection pass, and the disk state manager no longer keeps a lock for every expired session. ([#7318](https://github.com/reflex-dev/reflex/issues/7318))
- `reflex db` commands only require `sqlalchemy` and `alembic`, so apps that use plain SQLAlchemy models without `sqlmodel` can run migrations again. ([#7322](https://github.com/reflex-dev/reflex/issues/7322))
- A page URL with a `self` query parameter (e.g. `/post?self=1`), or a request header named `self`, no longer crashes router data parsing and leaves the page unhydrated. ([#7324](https://github.com/reflex-dev/reflex/issues/7324))
- `reflex run` now stops its frontend on SIGTERM and SIGINT without a TTY, while keeping frontend workers in the CLI process group so a hard kill also stops them. ([#7328](https://github.com/reflex-dev/reflex/issues/7328))
- A state stored in Redis that can no longer be unpickled, for example because a deploy moved or deleted a class held in a state var, is now replaced with a fresh state like a schema mismatch, instead of failing every event from that tab until the Redis key expires. ([#7329](https://github.com/reflex-dev/reflex/issues/7329))
- On Windows, the development backend no longer closes its listening socket twice when it releases the port, which could close another socket that had reused the handle and make it fail with `OSError: [WinError 10038]`. ([#7348](https://github.com/reflex-dev/reflex/issues/7348))
- `reflex run --json` now emits every output line as a JSON record: `print()` output from the app, subprocess output, and worker tracebacks (as one record with an `exception` field) no longer break the JSON-lines stream. ([#7350](https://github.com/reflex-dev/reflex/issues/7350))
- Fix a race with `REFLEX_OPLOCK_ENABLED` where an instance could take an opportunistic lease before its Redis lock notifications were active, making other instances wait out the full hold time for the same token. ([#7372](https://github.com/reflex-dev/reflex/issues/7372))
- Stop logging `asyncio.CancelledError: lifespan_cleanup` as an error when a running coroutine lifespan task is cancelled at backend shutdown or hot reload. ([#7392](https://github.com/reflex-dev/reflex/issues/7392))

### Performance

- Speed up first page loads by combining hydration with the websocket connect and sending only values that differ from compiled defaults. Reduce Redis state-tree read/write overhead and avoid repeated class metadata computation in apps with many states. ([#7064](https://github.com/reflex-dev/reflex/issues/7064))
- Reuse unchanged memo-body analysis during module emission to reduce repeated rendering and artifact collection. ([#7123](https://github.com/reflex-dev/reflex/issues/7123))
- Skip the linked-client fan-out on events that changed nothing shared, so an app that defines an `rx.SharedState` no longer resolves the running `App` on every event. ([#7237](https://github.com/reflex-dev/reflex/issues/7237))
- Reading a state var is about 4x faster, and setting one about 7x faster (15x in prod mode): vars, computed vars and event handlers are now descriptors on the state class that declares them, instead of every attribute access going through `BaseState.__getattribute__`. ([#7312](https://github.com/reflex-dev/reflex/issues/7312))
- Process events with less CPU on the backend: iterating, sorting and reading list and dataclass state values costs 25–75% less, and the redis state manager writes the changed states of a session in one round trip. ([#7370](https://github.com/reflex-dev/reflex/issues/7370))

### Documentation

- Document the dict form for `rx.toast` `action` and `cancel` props instead of referencing the non-public `ToastAction` class. ([#7327](https://github.com/reflex-dev/reflex/issues/7327))

### Miscellaneous

- No longer set `BUN_OPTIONS` when launching the frontend dev server; bun ignores it for the process it spawns for a package script. ([#7203](https://github.com/reflex-dev/reflex/issues/7203))
- Allow wrapt 2.4 and 2.5, and keep SQLModel below 0.0.45 to preserve existing datetime storage behavior. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-base (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Breaking Changes

- Remove `reflex_base.constants.CustomComponents`, which only the removed `reflex component` CLI used. ([#6425](https://github.com/reflex-dev/reflex/issues/6425))
- `PageContext.get()` and `CompileContext.get()` now raise `LookupError` instead of `RuntimeError` when no context is active, the same as every other `BaseContext` subclass. Compiler plugins that catch `RuntimeError` around these calls should catch `LookupError`. ([#6553](https://github.com/reflex-dev/reflex/issues/6553))
- `reflex_base.utils.types.is_backend_base_variable` and `RESERVED_BACKEND_VAR_NAMES` are removed: whether a state var is a backend var is now a property of its `Field` in `get_fields()`. By convention, fields named with a leading `_` are backend vars. `is_mutable_type` moved to `reflex_base.utils.types` (still importable from `reflex.istate.proxy`). ([#7312](https://github.com/reflex-dev/reflex/issues/7312))

### Features

- `SQLALCHEMY_POOL_TIMEOUT`, `REFLEX_BACKEND_COLD_START_TIMEOUT`, `REFLEX_SOCKET_INTERVAL` and `REFLEX_SOCKET_TIMEOUT` are `timedelta` settings, so they accept a unit suffix such as `REFLEX_SOCKET_TIMEOUT=2m`. A bare number is still read as seconds, so existing values keep their meaning. ([#7138](https://github.com/reflex-dev/reflex/issues/7138))
- `REFLEX_AUTO_RELOAD_COOLDOWN`, `REFLEX_OPLOCK_HOLD_TIME` and `REFLEX_STATE_MANAGER_DISK_DEBOUNCE` replace `REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS`, `REFLEX_OPLOCK_HOLD_TIME_MS` and `REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS`, and take a duration such as `250ms` or `5m`. The old names still work and keep counting the unit in their name, with a deprecation warning; they are removed in 1.0. ([#7138](https://github.com/reflex-dev/reflex/issues/7138))
- Add the `REFLEX_REDIS_MAX_CONNECTIONS` and `REFLEX_REDIS_POOL_TIMEOUT` environment variables for bounding each asynchronous Redis client's connection pool. A configured cap must be at least 3 to leave room for the token manager's two pub/sub listeners and ordinary commands; the pool wait defaults to 2 seconds and must be above 0 and shorter than the state-lock lifetime. ([#7179](https://github.com/reflex-dev/reflex/issues/7179))
- Add `Var.deep_equals()` for structural comparison of nested frontend values. ([#7208](https://github.com/reflex-dev/reflex/issues/7208))
- `Field` is now the descriptor holding a state var's value, and `EventHandler` binds to the state that declares it when accessed on a state instance. ([#7312](https://github.com/reflex-dev/reflex/issues/7312))
- Add `reflex_base.utils.log.supervise_output()`, which runs a command with its stdout and stderr on pipes and writes every line it and its descendants print as a JSON record; lines that already are JSON log records pass through unchanged. Output that a descendant writes after the command exits is forwarded for at most a few seconds. ([#7350](https://github.com/reflex-dev/reflex/issues/7350))

### Bug Fixes

- Auto-memoized `@rx.memo` wrapper names no longer repeat the wrapped memo component's tag. ([#7004](https://github.com/reflex-dev/reflex/issues/7004))
- Deprecation warnings no longer point at a pseudo-location such as `<string>` or `<frozen importlib._bootstrap>` when the deprecated call runs inside generated or frozen code; the location now names the first real user file. ([#7138](https://github.com/reflex-dev/reflex/issues/7138))
- Form submissions retain ID-backed controls with unset values while omitting IDs from non-controls. ([#7227](https://github.com/reflex-dev/reflex/issues/7227))
- `Var._replace(_var_data=...)` no longer raises `TypeError: dataclasses.replace() got multiple values for keyword argument '_var_data'`. ([#7256](https://github.com/reflex-dev/reflex/issues/7256))
- Flatten nested client event lists before dispatch and keep processing queued events after one event fails. ([#7319](https://github.com/reflex-dev/reflex/issues/7319))
- `rx.download(data=State.var)` percent-encodes the JSON it puts in the `data:` URL, so a `#` or `%` in the data no longer truncates or corrupts the downloaded file. ([#7325](https://github.com/reflex-dev/reflex/issues/7325))
- Negative-step slices of array and string Vars now match Python at a `-1` bound (e.g. `State.items[-1::-1]` no longer renders an empty list), and a Var step (e.g. `State.items[::State.step]`) no longer raises `RecursionError`. ([#7326](https://github.com/reflex-dev/reflex/issues/7326))
- A state that mixes in `abc.ABC` or another `ABCMeta` class (`class MyMixin(ABC, rx.State, mixin=True)`) no longer fails with a `StateValueError` claiming `_abc_impl` is reserved by `BaseState`. ([#7339](https://github.com/reflex-dev/reflex/issues/7339))
- Events sent while a buffered upload (or another `EventProcessor.enqueue_stream_delta` stream) is in flight are no longer chained to it: an uploading client that disconnects no longer cancels other clients' events, the upload's response no longer waits for them, and navigating during an upload cancels the previous page's unfinished `on_load` handlers again. Concurrent buffered uploads no longer hang or end each other's responses early. ([#7357](https://github.com/reflex-dev/reflex/issues/7357))
- State changes made after a buffered upload's response has ended, such as by events a backend exception handler chains after the upload handler fails, now reach the client instead of being silently dropped. ([#7357](https://github.com/reflex-dev/reflex/issues/7357))
- OpenTelemetry spans of top-level events enqueued during an HTTP request (a chunked upload, or a custom API route calling `app.event_processor.enqueue`) no longer carry a `reflex.event.parent_txid` naming the event processor's root context; only chained events name the event that produced them. ([#7358](https://github.com/reflex-dev/reflex/issues/7358))
- Pages in apps with many substates no longer intermittently fail to server-render with a 500 such as `SyntaxError: Invalid regular expression: /[^a-z-]/: Stack overflow`. ([#7369](https://github.com/reflex-dev/reflex/issues/7369))
- Calling an event handler of up to four arguments on the state class with its arguments, plain or as Vars, and passing such a handler where a callable of its arguments is expected now type-check under ty, as they already did under pyright. Calls of handlers with five or more arguments can still be misreported by ty. ([#7414](https://github.com/reflex-dev/reflex/issues/7414))

### Performance

- Reduce event-queue overhead when prepending events and processing events with a connected socket. ([#7053](https://github.com/reflex-dev/reflex/issues/7053))
- Begin opening the websocket transport before React mounts, then hydrate with a single `hydrate_and_load` event sent along with the websocket connect to save a round trip. ([#7064](https://github.com/reflex-dev/reflex/issues/7064))
- Evaluate generated passthrough memo bodies once and retain their render and artifacts so module emission does not repeat the work. ([#7123](https://github.com/reflex-dev/reflex/issues/7123))
- Reading a cached computed var no longer re-validates its return type, and in production mode state var assignments and computed var results check only the outer type instead of walking every element. The type checks only log errors, so this changes no behavior beyond fewer element-level log messages in production. ([#7353](https://github.com/reflex-dev/reflex/issues/7353))
- Building Vars (operations, comparisons, `rx.cond`, `rx.foreach`) is up to twice as fast, so pages that derive many Vars compile faster; the generated code is unchanged. ([#7370](https://github.com/reflex-dev/reflex/issues/7370))
- Lower the CPU cost of every backend event: cached computed var reads, field reads and writes, event dispatch and the JSON encoding of state deltas are faster. A computed var returning a value of the wrong type is now logged once per computed value instead of on every read, and `EventHandler.is_background` and `EventHandler.supersedes` are read once per handler, so mark the function before the handler is first used. ([#7370](https://github.com/reflex-dev/reflex/issues/7370))

### Miscellaneous

- Add the `routes.json` manifest name constant, written at compile time so the prod static file server can tell routable SPA paths from unknown ones. ([#6996](https://github.com/reflex-dev/reflex/issues/6996))
- Route log records from the new `reflex-workflow` package through the Reflex logger, so they follow the configured log level and sinks. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Update generated apps to React 19.3, Vite 8.3.2, Socket.IO client 4.8.4, Autoprefixer 10.6.1, and PostCSS 8.5.29. Update the bundled Bun runtime to 1.4.2. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-build-sdk (origin/r/pre-2026.10.05-37378928999)

## v0.0.5 (2026-09-24)

### Features

- Response models carry the fields the API returns that they previously dropped: `App` gains `backend_url`, `disable_secrets`, `weekly_report_enabled`, `source_thread_id`, `unreleased_provider` and the `any_environment_*` flags; `AppDeployment` gains `strategy`, `persistent` and `screenshot_uri`; `DeploymentRecord` gains `updated_by` and `promoted_from_id`; `ProjectAppDeployment` gains `updated_at`, `updated_by` and the `vm_type_*` fields; `Project` gains the `org_*` usage fields; `ProjectApp` gains `from_builder`; `ProjectMember` gains `role_permissions`; `AppSummary` gains `disable_secrets`; and `LogRecord` gains `event_id`, `stream_id` and `revision_id`. ([#7311](https://github.com/reflex-dev/reflex/issues/7311))

# reflex-components-code (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Miscellaneous

- Update Shiki and its transformers to 4.5.0. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-components-core (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Features

- The connection banner reads `REFLEX_BACKEND_COLD_START_TIMEOUT` as a duration, so it accepts a unit suffix such as `30s`. A bare number is still read as seconds. ([#7138](https://github.com/reflex-dev/reflex/issues/7138))

### Bug Fixes

- Fix `rx.match` raising `ReferenceError: Can't find variable` at render when a state Var is used only in a case condition with component branches. ([#6675](https://github.com/reflex-dev/reflex/issues/6675))
- Exclude IDs on forms and other non-controls from form submissions while preserving unset ID-backed controls and supporting custom controls marked with `_is_form_control`. ([#7227](https://github.com/reflex-dev/reflex/issues/7227))
- Require reflex-base 0.9.12 or newer so all imported rendering APIs are available. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))

### Miscellaneous

- Update react-dropzone to 17.0.0 and react-error-boundary to 6.1.6. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-components-dataeditor (origin/r/pre-2026.10.05-37378928999)

## v0.9.3 (2026-09-21)

### Features

- Ensure `rx.data_editor` image previews include Glide Data Grid's required carousel styles. ([#7081](https://github.com/reflex-dev/reflex/issues/7081))

# reflex-components-gridjs (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Require reflex-base 0.9.12 or newer so all imported rendering APIs are available. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))

# reflex-components-lucide (origin/r/pre-2026.10.05-37378928999)

## v1.0.4 (2026-08-28)

### Miscellaneous

- Internal logging migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))

# reflex-components-markdown (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Require reflex-base 0.9.12 or newer so all imported rendering APIs are available. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))

# reflex-components-moment (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Miscellaneous

- Update Moment to 2.31.0, moment-timezone to 0.6.5, and moment-duration-format to 2.3.2. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-components-plotly (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Normalize string Plotly layout titles to the `{"title": {"text": "..."}}` format required by Plotly.js. ([#7226](https://github.com/reflex-dev/reflex/issues/7226))

# reflex-components-radix (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Require reflex-base 0.9.12 or newer so all imported rendering APIs are available. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))

### Miscellaneous

- Update the Radix slider and progress dependencies to 1.4.7 and 1.1.16. ([#7424](https://github.com/reflex-dev/reflex/issues/7424))

# reflex-components-react-player (origin/r/pre-2026.10.05-37378928999)

## v0.9.2 (2026-08-28)

### Miscellaneous

- Internal logging migrated from the legacy console helpers to standard python `logging` per-module loggers. ([#6864](https://github.com/reflex-dev/reflex/issues/6864))

# reflex-components-recharts (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Require reflex-base 0.9.12 or newer so all imported rendering APIs are available. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))
- Allow Recharts axis tick formatters to use Reflex function vars. ([#7366](https://github.com/reflex-dev/reflex/issues/7366))

# reflex-components-sonner (origin/r/pre-2026.10.05-37378928999)

## v0.9.4 (2026-09-21)

### Bug Fixes

- Fix `rx.toast` `action` and `cancel` buttons not triggering their `on_click` events when the toast is fired from a frontend event trigger. ([#7157](https://github.com/reflex-dev/reflex/issues/7157))

# reflex-docgen (origin/r/pre-2026.10.05-37378928999)

## v0.10.0a1 (2026-10-05)

### Bug Fixes

- Recognize YAML frontmatter after a UTF-8 BOM or leading whitespace and with CRLF line endings, keeping metadata out of rendered page content and tables of contents. ([#7238](https://github.com/reflex-dev/reflex/issues/7238))

# reflex-hosting-cli (origin/r/pre-2026.10.05-37379302664)

## v0.1.73a1 (2026-10-05)

### Breaking Changes

- Some `reflex cloud` commands changed what they report. A refused request now exits non-zero rather than printing a `"... failed: ..."` line and exiting 0, and `--json` writes no document on that path; `apps stop`, `apps start` and `apps delete` are the ones most likely to be scripted against, and they now report their own outcome rather than echoing the server's sentence. `vmtypes` and `regions` answered a failed request with an empty listing and exit 0, which a script could not tell from a control plane that offers neither; they exit non-zero now. `apps history --json` replaces `hostname` with the deployment's `url`, reports `vm type` as the machine's name rather than an object, and reports `timestamp` as an ISO 8601 string with an offset; `apps inspect --json` drops `hostname` from `latest_deployment` the same way, the URL carrying it already. `create-token --json` replaces `expires_in_days` with `expires_at`, an ISO 8601 string or `null`, carrying the expiry the server applied rather than the duration that was asked for. `apps logs` drops its inert `--cursor` option and its `--json` document returns every line in the window rather than one page. `project role-permissions` lists permission names rather than objects. `reflex deploy` now requires a control plane that signs upload URLs; the multipart fallback for older ones is gone, and with it the "payload is too large (over 100MB)" hint, which only that path could produce. And `apps status --watch --json` reports `"success": null` when the watch stopped before the deployment ended -- it is still running, and the command did not see how it finished -- rather than answering `true` or `false` for something it does not know. ([#7207](https://github.com/reflex-dev/reflex/issues/7207))

### Bug Fixes

- `reflex cloud` reports a refusal as the sentence the API wrote rather than a message of its own, and an expired token now says to run `reflex login` wherever it turns up — not only where a command started by authenticating. ([#7207](https://github.com/reflex-dev/reflex/issues/7207))
- `reflex cloud apps delete` now exits non-zero when the app ID is not found. ([#7295](https://github.com/reflex-dev/reflex/issues/7295))
- With `--no-interactive`, a rejected access token now fails right away with the same message `reflex cloud whoami` gives, instead of starting the browser login. ([#7298](https://github.com/reflex-dev/reflex/issues/7298))
- Preserve a different stored access token when authentication rejects an outdated or explicitly supplied token. ([#7321](https://github.com/reflex-dev/reflex/issues/7321))
- `reflex deploy` now consistently shows the "Built with Reflex" badge on apps deployed on the free tier, including apps built with earlier reflex releases. Paid plans can still hide it with `show_built_with_reflex=False`. ([#7333](https://github.com/reflex-dev/reflex/issues/7333))
- `reflex cloud apps list`, `apps history` and `apps inspect` keep app names and app and deployment IDs whole on one line, so you can copy them from a normal-width terminal. `apps list` and `apps history` show fewer columns; `--json` still returns every field. `apps inspect` shows one field per row. Tables no longer draw cell borders. ([#7351](https://github.com/reflex-dev/reflex/issues/7351))
- `reflex cloud secrets update` now prints a success line naming the keys it set and whether the app is rebooting, like `secrets delete` already did. Only key names are printed; values are never logged. ([#7352](https://github.com/reflex-dev/reflex/issues/7352))
- Fail `reflex deploy` before building when an explicitly requested project does not exist or does not own the selected app. Accept equivalent UUID spellings, including uppercase and unhyphenated project IDs. ([#7355](https://github.com/reflex-dev/reflex/issues/7355))

### Miscellaneous

- `reflex-hosting-cli` now talks to Reflex Build through `reflex-build-sdk` rather than its own HTTP layer, so every command shares the SDK's retries, timeouts and typed errors. While the SDK is pre-1.0, where any release may change its API, the requirement is capped to the single patch line the CLI was built against, so upgrade `reflex-hosting-cli` to move to a newer SDK rather than upgrading the SDK on its own. ([#7207](https://github.com/reflex-dev/reflex/issues/7207))

# reflex-otel (origin/r/pre-2026.10.05-37378928999)

## v0.1.0 (2026-09-11)

### Features

- Add the `reflex-otel` package: an OpenTelemetry instrumentor that turns on the framework's built-in trace points and metrics (one span per event handler run, chained events parented under the enqueuing span, frontend `traceparent` propagation, event/state/websocket metrics, compile spans) and wraps the ASGI app in the OpenTelemetry ASGI middleware. `OtelPlugin(endpoint=...)` adds browser tracing (a `traceparent` on sampled events and uploads, web vitals, React render timing) to the compiled frontend; without an endpoint nothing is exported. Failed browser exports (for example a collector without CORS) are reported through the app's `frontend_exception_handler`. ([#6227](https://github.com/reflex-dev/reflex/issues/6227))

### Documentation

- Correct the environment-variable setup example to select HTTP/protobuf for the installed OTLP HTTP exporter. ([#7086](https://github.com/reflex-dev/reflex/issues/7086))

# reflex-release (origin/r/pre-2026.10.05-37379302664)

## v0.1.2a1 (2026-10-05)

### Bug Fixes

- Dispatch release forms keep their per-package checkboxes up to 24 packages, rather than falling back to a free-text field past 19. `workflow_dispatch` has accepted 25 inputs since December 2025. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))

# reflex-enterprise (r/pre-2026.10.05)

User-specified enterprise release; see enterprise report.