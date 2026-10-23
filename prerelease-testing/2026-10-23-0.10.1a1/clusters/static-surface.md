# Cluster `static-surface` — typing, imports, API/breaking surface, downstream names (NO dev server needed)

## Changelog lines (verbatim)
- (reflex-base #7401) An event handler stored outside a state, e.g. in a component or dataclass field, now type-checks as the handler instead of a bound function, and a handler read through a state instance is typed as a function returning `Any`.
- (reflex-base #7419) Calling an upload handler with `rx.upload_files(...)` or `rx.upload_files_chunk(...)` as its only argument now type-checks under pyright and ty.
- (reflex-base #7413) ty now reads an optional model, dataclass or mapping field (`rx.Field[X | None]`) on the state class as `ObjectVar[X]`, as pyright already did.
- (reflex #7406) Type checkers see the database helpers of `reflex.model` (`rx.session`, `rx.asession`, `rx.Model`, `ModelRegistry`, ...) as defined, rather than as unions with the stand-ins used when the db extra is missing.
- (reflex #7440) `reflex.model` (and `rx.ModelRegistry`, `rx.session`, `rx.Model`) can be imported without `greenlet`; only `rx.asession` and `get_async_engine` require it now.
- (reflex-base #7547) A state var annotation that names an undefined symbol raises `NameError: name 'Item' is not defined` again instead of an unrelated `TypeError` or `AttributeError`. Also covers vars without a default, backend vars, and Python 3.14 annotations without the `__future__` import.
- (reflex-base #7592) Resolve Pydantic v2 model field types without emitting deprecation warnings, while retaining Pydantic v1 compatibility.
- (reflex-base #7636) Event handler arguments hinted as an `rx.Model` no longer emit a `PydanticDeprecatedSince20` warning for every key of the payload.
- (reflex-base #7607, DEPRECATION) `reflex_base.utils.format.format_data_editor_column` is deprecated and will be removed in 1.0.
- (reflex-base #7586, DEPRECATION) `VarData(position=...)` and `Hooks.HookPosition` are deprecated and ignored.
- (reflex-components-radix #7555) Remove the `as_child` prop from `rx.radio_cards.root` and `rx.radio_cards.item`.
- (reflex #7614, BREAKING) `router.session.client_ip` now ignores untrusted `X-Forwarded-For` headers by default.
- (reflex #7443) Raise an actionable error when a legacy string passed to `App.modify_state()` has a missing or unknown state path.
- (reflex-base #7626, DOCS) Document the supported `BaseStateMeta` contract for custom state metaclasses, including the `state_root` and `mixin` class keywords.
- (reflex-build-sdk #7463) Expose `reflex_build_sdk.transports.default_transport()`.
- (reflex-hosting-cli #7340/#7390/#7434/#7463/#7546/#7452) CLI output/retry changes — only the offline-testable parts: `reflex cloud --help`, `reflex login --help`, behavior with an invalid `REFLEX_ACCESS_TOKEN` against an unreachable control plane (should suggest retry vs re-login appropriately).

## What to do
1. API diff: in a neutral dir, with `$SB/envs/prev/bin/python` and `$SB/envs/shared/bin/python`, dump `dir(reflex)`, `dir(reflex.components...)`, every `rx.*` namespace member, `reflex_base` public modules, plus the public names of `reflex.utils`, `reflex.event`, `reflex.vars` etc. (walk `pkgutil` over installed packages, import each module, record public names). Diff 0.10.0 vs 0.10.1a1; every REMOVED name that the changelog does not announce is a finding; every added public name should be documented.
2. Downstream grep: `uv pip download --no-deps reflex-enterprise reflex-local-auth reflex-global-hotkey reflex-ag-grid` (latest published) into a fresh dir, unzip, grep for `HookPosition`, `VarData(position`, `format_data_editor_column`, `as_child` on radio_cards, `client_ip`, `modify_state(`, `.position`, and any removed name from step 1. Also actually `pip install` each downstream package into its own venv alongside `reflex==0.10.1a1` (`--prerelease=allow`) and `import` it; report resolution conflicts (e.g. a downstream pin like `reflex<0.10.1`).
3. Typing: write small modules for each typing item above and run `uvx pyright --pythonpath <venv>` and `uvx ty check --python <venv>` against the shared venv; report false positives. Run the same against prev for baseline.
4. Runtime import checks (with `-W error::DeprecationWarning` where relevant): import `reflex.model` in a venv WITHOUT greenlet (uninstall it) — must succeed; `rx.asession` must raise a clear error. Define a state with `items: list[Item] = []` under `from __future__ import annotations` with `Item` undefined on Python 3.11 and 3.14 — expect NameError. Pydantic v2 model as handler arg → run an event through `app` (use `AppHarness`-free approach: construct state and call `_process_event`, or just instantiate state and check `warnings`), no `PydanticDeprecatedSince20`. Try pydantic v1 compat if installable (`pydantic<2` with reflex 0.10.1a1 — report if it does not resolve).
5. Deprecation surface: use `HookPosition`, `VarData(position=...)`, `format_data_editor_column`, `rx.radio_cards.root(as_child=True)`, and `rx.input(id="x")` in a form with an on_submit; capture the exact warning/error text and judge whether it points to the replacement.
6. `App.modify_state("bad.path")` → error text quality; `rx.BaseStateToken(...)` works.
7. Breaking: write an ASGI-level test (httpx/websockets to a backend started with `reflex run --backend-only` on your ports) sending `X-Forwarded-For` and compare `client_ip` with 0.10.0 vs 0.10.1a1, default and with `trusted_proxy_hops=1` in rxconfig. (The `headers-ip` cluster covers this more deeply; here just confirm the breaking change is real and documented.)
8. Install from sdist: `uv pip install --no-binary reflex --prerelease=allow reflex==0.10.1a1` into a fresh venv (#7411) — must resolve and import.
