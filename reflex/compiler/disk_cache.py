"""Disk-persisted incremental compile cache for ``REFLEX_COMPILE_CACHE``.

The manifest stores only bookkeeping: a file table (content hash plus stat key
per dependency file), each page's dependency paths, app-wrap keys, statefulness
and its contribution to the contexts file, the app-wide frontend imports, and
the import-name parse cache. Rendered files stay in ``.web``. When global
inputs and routes still match, unchanged pages are reused from disk and only
dependency-changed pages are recompiled.

Validation is stat-first (see :class:`page_cache.FileValidator`): an unchanged
file is recognised from ``(mtime_ns, size)`` without being read, and when the
watcher reports which paths changed, pages depending on none of them are hits
without even a stat.

"""

from __future__ import annotations

import base64
import contextlib
import dataclasses
import hashlib
import json
import logging
import pickle
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base import constants
from reflex_base.components.dynamic import record_bundle_requests
from reflex_base.environment import environment
from reflex_base.plugins import CompileContext, CompilerHooks, Plugin
from reflex_base.registry import RegistrationContext
from reflex_base.utils import log
from reflex_base.utils.format import json_dumps
from reflex_base.utils.imports import ImportVar, merge_imports

from reflex.compiler import page_cache
from reflex.compiler.plugins import default_page_plugins
from reflex.utils import console, path_ops, prerequisites

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from reflex_base.plugins import PageContext, PageDefinition
    from reflex_base.utils.imports import ParsedImportDict

    from reflex.app import App
    from reflex.compiler import utils as compiler_utils

logger = logging.getLogger(__name__)

#: Bump when the manifest layout changes (old manifests are then ignored).
_SCHEMA = 22
#: Manifest filename under the web directory.
_MANIFEST_FILE = "reflex_compile_cache.json"

#: Paths the watcher reported as changed for the current compile, resolved.
#: None when unknown (a cold start or a cache-less compile), in which case
#: every recorded dependency is validated.
_changed_hint: set[str] | None = None


def set_changed_hint(paths: Iterable[Path | str] | None) -> None:
    """Tell the next incremental rebuild which paths the watcher saw change.

    Args:
        paths: The changed paths, or None when unknown.
    """
    global _changed_hint
    _changed_hint = None if paths is None else {str(Path(p).resolve()) for p in paths}


#: Whether this compile predicts the ``reflex.istate.dynamic`` state names of
#: the pages it does not re-evaluate, instead of re-evaluating every page that
#: defines such states (see :func:`_with_dynamic_state_pages`). Only a caller
#: that can discard this process and compile again sets it.
_predict_dynamic_names = False


def set_dynamic_name_prediction(enabled: bool) -> None:
    """Predict dynamic state names in this process's compiles.

    A failed prediction raises :class:`DynamicStatePredictionError`; the
    caller then compiles again in a fresh process without prediction.

    Args:
        enabled: Whether to predict.
    """
    global _predict_dynamic_names
    _predict_dynamic_names = enabled


class DynamicStatePredictionError(Exception):
    """A predicted rebuild cannot finish correctly in this process.

    Either a re-evaluated page claimed other ``reflex.istate.dynamic`` names
    than recorded, which shifts the names of pages that were not
    re-evaluated, or a fallback would evaluate further pages out of page
    order. Compile again in a fresh process without prediction.
    """


def _manifest_path() -> Path:
    return prerequisites.get_web_dir() / _MANIFEST_FILE


def format_path_list(
    items: Iterable[str], root: Path | None = None, limit: int = 5
) -> str:
    """Render a bounded, root-relative summary of a path/label collection.

    Args:
        items: The paths (or labels) to render.
        root: When given, paths under it are shown relative to it.
        limit: Maximum number of entries to show before truncating.

    Returns:
        A comma-separated summary string, truncated with ``(+N more)``.
    """

    def rel(item: str) -> str:
        if root is not None:
            with contextlib.suppress(ValueError):
                return str(Path(item).relative_to(root))
        return item

    shown = sorted(rel(item) for item in items)
    extra = len(shown) - limit
    return ", ".join(shown[:limit]) + (f" (+{extra} more)" if extra > 0 else "")


def _log_fallback(reason: str) -> None:
    """Report why the incremental rebuild fell back to a full compile.

    Args:
        reason: The human-readable fallback reason.
    """
    logger.info(f"Compile cache: falling back to a full compile — {reason}")


_IMPORT_VAR_FIELDS = tuple(f.name for f in dataclasses.fields(ImportVar))


def _serialize_imports(imports: ParsedImportDict) -> dict[str, list[dict[str, Any]]]:
    """Serialize a parsed import dict to JSON-able primitives.

    Duplicates are collapsed in first-seen order (a full docs-app compile
    accumulates ~107k entries, ~6k unique): the manifest's import set only
    feeds package installation and later merges, where only the unique set
    matters, and duplicates bloat the manifest and every pass over it.

    Args:
        imports: The parsed import dict to serialize.

    Returns:
        A JSON-serializable representation.
    """
    return {
        lib: [
            {name: getattr(iv, name) for name in _IMPORT_VAR_FIELDS}
            for iv in dict.fromkeys(ivs)
        ]
        for lib, ivs in imports.items()
    }


def _deserialize_imports(data: dict[str, list[dict[str, Any]]]) -> ParsedImportDict:
    """Rebuild a parsed import dict from its serialized form.

    Args:
        data: The serialized import dict.

    Returns:
        The reconstructed parsed import dict.
    """
    return {lib: [ImportVar(**iv) for iv in ivs] for lib, ivs in data.items()}


def _wrap_key_str(key: tuple[int, str]) -> str:
    """Format an app-wrap key for the manifest.

    Args:
        key: The ``(priority, name)`` app-wrap key.

    Returns:
        ``"<priority>:<name>"``.
    """
    return f"{key[0]}:{key[1]}"


def _wrap_key(key_str: str) -> tuple[int, str]:
    """Parse an app-wrap key formatted by :func:`_wrap_key_str`.

    Args:
        key_str: The formatted key.

    Returns:
        The ``(priority, name)`` app-wrap key.
    """
    priority, _, name = key_str.partition(":")
    return int(priority), name


def _wrap_digest(component: Any) -> str:
    """Digest what an app wrap contributes to the compiled app root.

    Args:
        component: The app-wrap component.

    Returns:
        A digest of its render, imports, hooks, custom code, dynamic imports
        and the app wraps its own subtree declares.
    """
    payload = [
        component.render(),
        _serialize_imports(component._get_all_imports()),
        list(component._get_all_hooks()),
        list(component._get_all_custom_code()),
        sorted(component._get_all_dynamic_imports()),
        sorted(map(_wrap_key_str, component._get_all_app_wrap_components())),
    ]
    return hashlib.sha256(json_dumps(payload).encode()).hexdigest()


def _stored_wrap(component: Any, digest: str) -> str | None:
    """Serialize an app wrap so the app root can be rebuilt without its page.

    Args:
        component: The app-wrap component.
        digest: Its :func:`_wrap_digest`.

    Returns:
        The encoded component, or None when it does not round-trip to the same
        contribution.
    """
    try:
        data = pickle.dumps(component)
        if _wrap_digest(pickle.loads(data)) != digest:
            return None
    except Exception:
        return None
    return base64.b64encode(data).decode()


def _record_app_wraps(
    page_ctx: PageContext, wrap_table: dict[str, str | None]
) -> dict[str, str]:
    """Record a page's app wraps by digest, interning each in the wrap table.

    Args:
        page_ctx: The compiled page context.
        wrap_table: The manifest's digest -> stored component table (extended).

    Returns:
        The page's app-wrap keys mapped to their digests, in page order.
    """
    wraps = {}
    for key, component in page_ctx.app_wrap_components.items():
        digest = _wrap_digest(component)
        if digest not in wrap_table:
            wrap_table[digest] = _stored_wrap(component, digest)
        wraps[_wrap_key_str(key)] = digest
    return wraps


def _state_libraries(initial_state: dict[str, Any]) -> dict[str, list[str]]:
    """Record the libraries serializing each state's initial values requests.

    Args:
        initial_state: Initial values keyed by state full name.

    Returns:
        The requested libraries of each state that requests any.
    """
    from reflex.compiler import utils as compiler_utils

    libraries = {}
    for name, values in initial_state.items():
        with record_bundle_requests() as requests:
            compiler_utils._serialize_initial_state({name: values})
        if requests:
            libraries[name] = requests
    return libraries


def _reconstruct_libraries(
    base: Sequence[str],
    page_requests: Sequence[Sequence[Sequence[str]]],
    root_requests: Sequence[str],
    state_libraries: dict[str, list[str]],
) -> list[str]:
    """Rebuild the bundled-library registry in full-compile order.

    A full compile evaluates every page, then renders every page, builds the
    app root and serializes the states in name order; the registry keeps the
    first request of each library.

    Args:
        base: The registry after the compile's reset.
        page_requests: ``[evaluate, render]`` requests of each page, in page
            order.
        root_requests: The requests made while building the app root.
        state_libraries: The requests of each state's initial values.

    Returns:
        The bundled libraries, in registry order.
    """
    ordered = [*base]
    for evaluate, _ in page_requests:
        ordered.extend(evaluate)
    for _, render in page_requests:
        ordered.extend(render)
    ordered.extend(root_requests)
    for name in sorted(state_libraries):
        ordered.extend(state_libraries[name])
    return list(dict.fromkeys(ordered))


def _stable_value(value: Any) -> Any:
    """Turn a page registration value into a process-independent JSON value.

    Args:
        value: A value ``add_page`` was given.

    Returns:
        A JSON-able value that is equal across processes for equal inputs.
    """
    from reflex_base.components.component import BaseComponent
    from reflex_base.vars import Var

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Var):
        return str(value)
    if isinstance(value, BaseComponent):
        return value.render()
    if isinstance(value, dict):
        return {str(key): _stable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _stable_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if callable(value):
        # Which function, not its body: a page function's body is a recorded
        # dependency of the page, and load events only run on the backend.
        return [
            getattr(value, "__module__", None),
            getattr(value, "__qualname__", None),
        ]
    return repr(value)


def _registration_digest(page: PageDefinition) -> str:
    """Digest everything a page was registered with.

    Args:
        page: The page definition.

    Returns:
        A digest of its route, metadata, load events and component.
    """
    return hashlib.sha256(json_dumps(_stable_value(page)).encode()).hexdigest()


def registration_digests(pages: Iterable[PageDefinition]) -> dict[str, str]:
    """Digest each page's registration before any page is evaluated.

    Evaluation mutates component instances passed as pages (styles are
    applied in place), so the digests are taken once, up front.

    Args:
        pages: The page definitions.

    Returns:
        Each route's registration digest.
    """
    return {page.route: _registration_digest(page) for page in pages}


def _manifest_page_entry(
    page_ctx: PageContext,
    page: PageDefinition,
    state_index: dict[str, Path],
    hasher: Callable[[str], page_cache.FileEntry | None],
    files: dict[str, page_cache.FileEntry],
    *,
    defined_states: Sequence[str] | None,
    registration: str,
    wrap_table: dict[str, str | None],
    state_slice: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Build the manifest entry for one compiled page.

    Args:
        page_ctx: The compiled page context.
        page: The page definition.
        state_index: The state-context identifier -> file index.
        hasher: A memoized path -> file-entry function.
        files: The manifest file table, extended with the page's dependencies.
        defined_states: Full names of the states the page defined while it
            evaluated, or None for a stateless page.
        registration: The page's registration digest (see
            :func:`registration_digests`).
        wrap_table: The manifest's app-wrap table, extended with the page's
            wraps.
        state_slice: The page's contribution to the contexts file
            (see :func:`_state_slice`), or None for stateless pages.
        root: Project root for dependency discovery. Defaults to cwd.

    Returns:
        The JSON-able manifest entry for the page.
    """
    from reflex.utils.telemetry_accounting import _count_components

    return {
        "component_counts": _count_components([page_ctx.root_component]),
        "deps": page_cache.page_dependency_entries(
            page_ctx, page.component, state_index, hasher, files, root
        ),
        # Everything the page was registered with (see ``partition_pages``).
        "registration": registration,
        # The app wraps the page requires, by digest (see ``_refresh_app_root``).
        "app_wraps": _record_app_wraps(page_ctx, wrap_table),
        # Libraries requested while evaluating and rendering the page.
        "bundle_requests": [
            page_ctx.evaluate_bundle_requests,
            page_ctx.render_bundle_requests,
        ],
        "is_stateful": defined_states is not None,
        "state_slice": state_slice,
        # The ``reflex.istate.dynamic`` names the page's states took, whose
        # suffixes depend on evaluation order (see ``_with_dynamic_state_pages``).
        "dynamic_claims": _dynamic_claims(defined_states or ()),
        # Whether the page contributed auto memos: pages sharing a source
        # module share one memo output file, so a memo-contributing hit page
        # must be recompiled alongside a same-module miss (see
        # ``_with_module_siblings``).
        "has_memos": bool(page_ctx.memo_contributions),
        # Where those auto memos are written, so removing the page rewrites it.
        "memo_path": (
            _memo_output_path(getattr(page, "_source_module", None))
            if page_ctx.memo_contributions
            else None
        ),
    }


def _state_slice(
    state_names: Sequence[str],
    initial_state: dict[str, Any],
    client_storage: dict[str, dict[str, Any]],
    schema_entries: dict[str, list[Any]],
) -> dict[str, Any]:
    """Extract some states' contribution to the compiled contexts file.

    A state's contribution is exactly its initial-state entry, its
    client-storage entries and its frontend schema entry (see
    ``templates.context_template``). Persisting the slice, not just a
    fingerprint, lets an incremental rebuild re-emit the contexts file for
    pages it did not evaluate (states only registered while their page
    evaluates, e.g. exec'd docs demos) without evaluating them.

    Args:
        state_names: Full names of the states to slice.
        initial_state: The complete initial-state mapping (full name -> vars).
        client_storage: The compiled client-storage mapping per storage kind.
        schema_entries: The frontend schema entries (full name -> entry).

    Returns:
        ``{"initial_state": {...}, "client_storage": {kind: {...}},
        "schema": {...}}``.
    """
    from reflex.compiler import utils as compiler_utils

    names = sorted(state_names)
    prefixes = tuple(f"{name}." for name in names)
    return {
        # Serialized as the contexts file holds them: a component value's code
        # depends on whether its library is bundled, which serializing does.
        "initial_state": {
            name: json.loads(
                compiler_utils._serialize_initial_state({name: initial_state[name]})
            )[name]
            for name in names
            if name in initial_state
        },
        "client_storage": {
            kind: {k: v for k, v in entries.items() if k.startswith(prefixes)}
            for kind, entries in client_storage.items()
        },
        "schema": {
            name: schema_entries[name] for name in names if name in schema_entries
        },
    }


def _slice_digest(state_slice: dict[str, Any] | None) -> str:
    """Hash a state slice for cheap equality.

    Args:
        state_slice: A :func:`_state_slice` result (or None).

    Returns:
        A stable digest.
    """
    return hashlib.sha256(json_dumps(state_slice).encode()).hexdigest()


def _contexts_snapshot(app: App | None) -> compiler_utils.ContextsSnapshot | None:
    """Capture the state-tree inputs of the contexts file.

    Args:
        app: The app being compiled (absent in bare compile contexts).

    Returns:
        The contexts snapshot of the app's state tree, or None when there is
        no state tree.
    """
    if app is None or app._state is None:
        return None
    from reflex.compiler import utils as compiler_utils

    return compiler_utils.compile_contexts_snapshot(app._state)


def _changed_state_config_route(
    manifest: dict[str, Any],
    miss_ctx: CompileContext,
    snapshot: compiler_utils.ContextsSnapshot | None,
    miss_routes: Iterable[str],
) -> str | None:
    """Find the first recompiled route whose contribution to contexts changed.

    Compares each recompiled page's just-evaluated states against the slice
    recorded in the manifest; a page without states contributes no slice, so
    gaining or losing states counts as a change. Only these pages' states can
    differ from the on-disk contexts file: hit pages' definitions are
    unchanged by construction (all their dependency files still match).

    Args:
        manifest: The loaded compile manifest.
        miss_ctx: The compile context of the recompiled pages.
        snapshot: The ``_contexts_snapshot`` of the app, or None when there is
            no state tree.
        miss_routes: The recompiled routes.

    Returns:
        The first route requiring a contexts rebuild, or None if none do.
    """
    for route in miss_routes:
        defined_states = miss_ctx.stateful_routes.get(route)
        live = (
            _state_slice(defined_states, *snapshot)
            if defined_states and snapshot is not None
            else None
        )
        if _slice_digest(manifest["pages"][route]["state_slice"]) != _slice_digest(
            live
        ):
            return route
    return None


def _with_hit_state_slices(
    snapshot: compiler_utils.ContextsSnapshot,
    manifest: dict[str, Any],
    miss_routes: set[str],
) -> compiler_utils.ContextsSnapshot:
    """Merge the stored contexts contributions of the stateful hit pages.

    Args:
        snapshot: The contexts snapshot of this process's state tree.
        manifest: The loaded manifest.
        miss_routes: Routes recompiled in this rebuild (their states are live).

    Returns:
        The snapshot of the live states plus the hit pages' stored states.
    """
    live_initial, live_storage, live_schema = snapshot
    initial = dict(live_initial)
    storage = {kind: dict(entries) for kind, entries in live_storage.items()}
    schema_entries = dict(live_schema)
    for route, entry in manifest["pages"].items():
        if route in miss_routes or not (state_slice := entry["state_slice"]):
            continue
        initial.update(state_slice["initial_state"])
        for kind, entries in state_slice["client_storage"].items():
            storage.setdefault(kind, {}).update(entries)
        schema_entries.update(state_slice["schema"])
    return dict(sorted(initial.items())), storage, schema_entries


def load_manifest() -> dict[str, Any] | None:
    """Load the persisted compile manifest, or None if absent/unusable.

    Also seeds the import-name parse cache from the manifest, so unchanged
    first-party modules are not re-parsed in this process.

    Returns:
        The parsed manifest dict, or None.
    """
    path = _manifest_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
        return None
    page_cache.load_import_names_cache(data.get("import_names", {}))
    return data


def manifest_dependency_files(manifest: dict[str, Any]) -> set[str]:
    """Every file the manifest records as a compile input.

    Args:
        manifest: The loaded manifest.

    Returns:
        Page dependency paths plus the file-backed global inputs.
    """
    files: set[str] = set()
    for entry in manifest.get("pages", {}).values():
        files.update(page_cache.dep_file(dep) for dep in entry.get("deps", ()))
    files.update(
        path for label, path in manifest.get("globals", {}).items() if label != "reflex"
    )
    files.update(manifest.get("globals_absent", ()))
    return files


def _write(manifest: dict[str, Any]) -> None:
    """Persist the manifest, including the current import-name parse cache.

    Args:
        manifest: The manifest to write.
    """
    manifest["import_names"] = page_cache.export_import_names_cache()
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(manifest), encoding="utf-8")


def write_manifest(
    compile_ctx: CompileContext,
    pages: Sequence[PageDefinition],
    install_imports: ParsedImportDict,
    root: Path | None = None,
    *,
    plugin_sources: dict[str, str] | None = None,
    contexts_snapshot: compiler_utils.ContextsSnapshot | None = None,
    root_bundle_requests: Sequence[str] = (),
    registrations: dict[str, str] | None = None,
) -> None:
    """Persist a manifest of the just-completed full compile.

    Best-effort: any failure leaves no manifest (the next compile is full), it
    never breaks the build.

    Args:
        compile_ctx: The completed compile context (all pages compiled).
        pages: The full list of page definitions that were compiled.
        install_imports: The **complete** frontend import set the full compile
            installed: page imports merged with the app-root (app-wrap, e.g.
            the Toaster/``sonner`` provider) and memo-component imports. An
            incremental rebuild reuses the on-disk app-wide files, so it must
            install from this complete set, not just the per-page union.
        root: Project root for fingerprinting. Defaults to cwd.
        plugin_sources: Unmodified source content for plugin file modifiers.
        contexts_snapshot: The state-tree inputs used for the contexts output.
            When absent, a snapshot is captured for direct callers.
        root_bundle_requests: The libraries requested while building the app
            root.
        registrations: Each route's registration digest, taken before any page
            evaluated; computed now when absent.
    """
    try:
        state_index, _ = page_cache.state_dependency_index(root)
        hasher = page_cache.make_hasher()
        files: dict[str, page_cache.FileEntry] = {}
        wrap_table: dict[str, str | None] = {}
        if registrations is None:
            registrations = registration_digests(pages)
        if contexts_snapshot is None and compile_ctx.stateful_routes:
            contexts_snapshot = _contexts_snapshot(compile_ctx.app)

        pages_data: dict[str, Any] = {}
        for page in pages:
            page_ctx = compile_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                logger.warning(
                    f"Compile cache: cannot save manifest because page {page.route!r} "
                    "has incomplete output. The next reload will need a full compile."
                )
                return  # incomplete compile -> do not write a partial manifest
            defined_states = compile_ctx.stateful_routes.get(page.route)
            pages_data[page.route] = _manifest_page_entry(
                page_ctx,
                page,
                state_index,
                hasher,
                files,
                defined_states=defined_states,
                registration=registrations[page.route],
                wrap_table=wrap_table,
                state_slice=(
                    _state_slice(defined_states, *contexts_snapshot)
                    if defined_states and contexts_snapshot is not None
                    else None
                ),
                root=root,
            )
        state_libraries = (
            _state_libraries(contexts_snapshot[0])
            if contexts_snapshot is not None
            else {}
        )
        libraries = list(RegistrationContext.ensure_context().bundled_libraries)
        reconstructed = _reconstruct_libraries(
            compile_ctx.bundle_base,
            [pages_data[page.route]["bundle_requests"] for page in pages],
            root_bundle_requests,
            state_libraries,
        )
        if reconstructed != libraries:
            logger.debug(
                "Compile cache: bundled libraries were requested outside the "
                "recorded phases; changes to the app root need a full compile."
            )

        # Post-evaluation and complete: the full compile evaluated every page,
        # so both import-owned and route-owned memos are recorded.
        memo_files = _memo_state_entries(hasher, files, root, lambda _owner: True)

        globals_: dict[str, str] = {"reflex": page_cache._reflex_version()}
        absent: list[str] = []
        global_paths = page_cache.global_input_paths(root, pages=pages)
        page_states = {
            name for names in compile_ctx.stateful_routes.values() for name in names
        }
        module_states = _record_module_states(
            (
                name
                for name in RegistrationContext.ensure_context().base_states
                if name not in page_states
            ),
            hasher,
            files,
            root,
        )
        for label, path in global_paths.items():
            entry = hasher(path)
            if entry is None:
                absent.append(path)
            else:
                files[path] = entry
                globals_[label] = path

        entry_file = page_cache._app_entrypoint_file(root)
        manifest = {
            "schema": _SCHEMA,
            # The app entry module apart from its page registrations (see
            # ``globals_mismatch``).
            "entry": {
                "path": None if entry_file is None else str(entry_file),
                "digest": (
                    None
                    if entry_file is None
                    else page_cache.entrypoint_digest(str(entry_file))
                ),
            },
            # File paths below are absolute: the manifest describes this
            # project directory only.
            "root": str((root or Path.cwd()).resolve()),
            "plugin_sources": plugin_sources or {},
            "reflex_version": page_cache._reflex_version(),
            "mode": _compile_mode(),
            "files": files,
            # Per-input labels (not one combined digest) so a later mismatch
            # can name the exact global input that changed.
            "globals": globals_,
            "globals_absent": sorted(absent),
            "all_imports": _serialize_imports(install_imports),
            "pages": pages_data,
            "memo_files": memo_files,
            "wrap_table": wrap_table,
            "state_libraries": state_libraries,
            # The states importing the app registers (see
            # ``_record_module_states``).
            "module_states": module_states,
            # The app root's inputs: merged app wraps (by digest, in insertion
            # order) and the bundled libraries (see ``_refresh_app_root``).
            "app_root": {
                "wraps": {
                    _wrap_key_str(key): _wrap_digest(component)
                    for key, component in compile_ctx.app_wrap_components.items()
                },
                "libraries": libraries,
                "root_requests": list(root_bundle_requests),
                "reconstructible": reconstructed == libraries,
            },
        }
        _write(manifest)
    except Exception as exc:  # best-effort: never break the build
        logger.warning(
            f"Compile cache: could not save manifest ({exc!r}). "
            "The next reload may need a full compile."
        )


def _compile_mode() -> str:
    """The compile mode the rendered output is specific to (``dev``/``prod``).

    Returns:
        The current ``REFLEX_ENV_MODE`` value.
    """
    return environment.REFLEX_ENV_MODE.get().value


def _module_state_files(state_names: Iterable[str], root: Path | None) -> set[str]:
    """Find the source files that define the given states, with their imports.

    Args:
        state_names: Full names of registered states.
        root: Project root for dependency discovery.

    Returns:
        First-party source files the states' definitions depend on.
    """
    roots = page_cache.first_party_roots(root)
    base_states = RegistrationContext.ensure_context().base_states
    sources = {
        str(path)
        for name in state_names
        if (path := page_cache._class_module_file(base_states[name], roots)) is not None
    }
    return page_cache._walk_import_closure(page_cache.build_import_graph(root), sources)


def _record_module_states(
    state_names: Iterable[str],
    hasher: Callable[[str], page_cache.FileEntry | None],
    files: dict[str, page_cache.FileEntry],
    root: Path | None,
) -> dict[str, list[str]]:
    """Record the states importing the app registers, and their source files.

    They belong to no page, so the contexts file depends on them directly.

    Args:
        state_names: Full names of the import-time states.
        hasher: A memoized path -> file-entry function.
        files: The manifest file table, extended with the source files.
        root: Project root for dependency discovery.

    Returns:
        ``{"names": [...], "files": [...], "dynamic": [...]}``.
    """
    import reflex.istate.dynamic as istate_dynamic

    names = sorted(state_names)
    recorded = []
    for path in sorted(_module_state_files(names, root)):
        if (entry := hasher(path)) is not None:
            files[path] = entry
            recorded.append(path)
    base_states = RegistrationContext.ensure_context().base_states
    return {
        "names": names,
        "files": recorded,
        # Import-time dynamic-module states, which take names before any page.
        "dynamic": [
            name
            for name in names
            if base_states[name].__module__ == istate_dynamic.__name__
        ],
    }


def globals_mismatch(
    manifest: dict[str, Any],
    *,
    validator: page_cache.FileValidator,
    root: Path | None = None,
) -> str | None:
    """Explain why the manifest's global inputs don't match, or None if they do.

    The fast rebuild needs the global inputs unchanged: Reflex version,
    config/lockfiles and the app-level config files (the entrypoint and the
    theme/app-wrap/stylesheet modules it imports, which configure the app-wide
    files). An entrypoint that only changed its page registrations still
    matches; the routes and registrations are then compared page by page.
    Everything else is decided per page via its dependency set, so a
    shared-component or markdown edit no longer blocks the fast path.

    Global inputs are validated against the manifest's *stored* input set,
    never by recomputing the set in this process — set membership is only
    decided when a full compile writes the manifest.

    Args:
        manifest: The loaded manifest.
        validator: The file validator bound to the manifest's file table.
        root: Project root the manifest must describe; also shortens paths in
            the reason. Defaults to cwd.

    Returns:
        A human-readable mismatch reason, or None when the global inputs match.
    """
    current_root = str((root or Path.cwd()).resolve())
    if manifest["root"] != current_root:
        return f"project root changed ({manifest['root']} -> {current_root})"
    old_version = manifest.get("reflex_version")
    if old_version != page_cache._reflex_version():
        return (
            f"reflex version changed ({old_version} -> {page_cache._reflex_version()})"
        )
    old_mode = manifest.get("mode")
    if old_mode != _compile_mode():
        return f"compile mode changed ({old_mode} -> {_compile_mode()})"
    root = (root or Path.cwd()).resolve()
    entry = manifest["entry"]
    stale = {
        label.removeprefix("app:")
        for label, path in manifest.get("globals", {}).items()
        if label != "reflex"
        and validator.changed(path)
        # An entry module that only changed its page registrations is compared
        # page by page (see ``partition_pages``).
        and not (
            path == entry["path"]
            and entry["digest"] is not None
            and page_cache.entrypoint_digest(path) == entry["digest"]
        )
    }
    stale.update(
        path for path in manifest.get("globals_absent", ()) if Path(path).is_file()
    )
    if stale:
        return f"global input(s) changed: {format_path_list(stale, root)}"
    return None


def _with_hinted_slices(
    changed_hint: set[str] | None, manifest: dict[str, Any]
) -> set[str] | None:
    """Add the recorded function slices of the files the watcher reported.

    Args:
        changed_hint: Resolved paths the watcher saw change, or None if unknown.
        manifest: The loaded manifest.

    Returns:
        The hint with every page dependency that reads a reported file.
    """
    if not changed_hint:
        return changed_hint
    return changed_hint | {
        dep
        for entry in manifest["pages"].values()
        for dep in entry["deps"]
        if page_cache.SLICE_SEPARATOR in dep
        and page_cache.dep_file(dep) in changed_hint
    }


def partition_pages(
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    validator: page_cache.FileValidator,
    changed_hint: set[str] | None,
    registrations: dict[str, str],
) -> list[PageDefinition]:
    """Return the pages that are new or changed since the manifest.

    Globals are assumed already matched (see :func:`globals_mismatch`), so a
    recorded page is a hit if it was registered the same way and every file
    in its recorded dependency set is unchanged. When the watcher reported the
    changed paths, a page depending on none of them skips the filesystem.

    Args:
        pages: The current page definitions.
        manifest: The loaded manifest.
        validator: The file validator bound to the manifest's file table.
        changed_hint: Resolved paths the watcher saw change, or None if unknown.
        registrations: Each route's registration digest.

    Returns:
        The list of miss pages (new, re-registered or a dependency changed).
    """
    manifest_pages = manifest["pages"]
    misses: list[PageDefinition] = []
    for page in pages:
        entry = manifest_pages.get(page.route)
        if entry is None or entry["registration"] != registrations[page.route]:
            misses.append(page)
            continue
        deps = entry["deps"]
        if changed_hint is not None and changed_hint.isdisjoint(deps):
            continue
        if not validator.unchanged(deps):
            misses.append(page)
    return misses


def _with_module_siblings(
    miss_pages: list[PageDefinition],
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
) -> list[PageDefinition]:
    """Expand the miss set with memo-contributing same-module hit pages.

    Auto-memo output is grouped into one file per source module, so rewriting
    that file needs the contributions of *all* the module's pages that have
    any. Hit pages that contributed no memos (per the manifest) have nothing
    in that file and are left reused.

    Args:
        miss_pages: The dependency-changed pages.
        pages: All current page definitions (in compile order).
        manifest: The loaded manifest.

    Returns:
        The expanded miss list, in ``pages`` order.
    """
    miss_modules = {
        module
        for page in miss_pages
        if (module := getattr(page, "_source_module", None)) is not None
    }
    if not miss_modules:
        return miss_pages
    miss_routes = {page.route for page in miss_pages}
    return [
        page
        for page in pages
        if page.route in miss_routes
        or (
            getattr(page, "_source_module", None) in miss_modules
            and manifest["pages"][page.route]["has_memos"]
        )
    ]


def _dynamic_claims(defined_states: Iterable[str]) -> list[list[str]]:
    """The ``reflex.istate.dynamic`` names a page's states took, in order.

    Each name is paired with what was requested: a local state's class name,
    or the ``ComponentState`` a per-instance state was created from. A page
    making the same claims as recorded took the names a full compile gives it.

    Args:
        defined_states: Full names of the states the page defined.

    Returns:
        ``[name, requested]`` pairs in definition order.
    """
    import reflex.istate.dynamic as istate_dynamic

    base_states = RegistrationContext.ensure_context().base_states
    claims = []
    for full_name in defined_states:
        cls = base_states[full_name]
        if cls.__module__ != istate_dynamic.__name__:
            continue
        requested = cls.__dict__.get("__original_name__")
        if requested is None:
            origin = cls.__bases__[0]
            requested = f"{origin.__module__}.{origin.__qualname__}"
        claims.append([cls.__name__, requested])
    return claims


_NAME_SUFFIX = re.compile(r"_\d+$")


def _claims_by_family(claims: Iterable[Sequence[str]]) -> dict[str, list[list[str]]]:
    """Group dynamic state name claims by the name family they draw from.

    A local state takes the first free name among its class name and its
    ``_<n>`` suffixes, so it competes with every claim whose name or request
    has the same stem. A ``ComponentState`` instance draws from its class's
    counter; its request is the dotted class path, which no class name has.

    Args:
        claims: ``[name, requested]`` pairs (see :func:`_dynamic_claims`).

    Returns:
        The claims of each family, in order.
    """
    families: dict[str, list[list[str]]] = {}
    for name, requested in claims:
        for family in {_NAME_SUFFIX.sub("", name), _NAME_SUFFIX.sub("", requested)}:
            families.setdefault(family, []).append([name, requested])
    return families


def _shifting_dynamic_claims(
    manifest: dict[str, Any],
    miss_ctx: CompileContext | None,
    miss_routes: set[str],
    removed_entries: dict[str, dict[str, Any]],
) -> str | None:
    """Find a changed page whose claims could shift other pages' names.

    Names in a family are handed out in evaluation order, so a re-evaluated,
    added or removed page changing its claims in a family moves the names of
    later pages in that family. Pages that were not re-evaluated keep their
    recorded names, which is exact only when no family they use changed.

    Args:
        manifest: The loaded manifest (without the removed pages).
        miss_ctx: The compile context of the re-evaluated pages, if any.
        miss_routes: The re-evaluated routes.
        removed_entries: The manifest entries of the removed routes.

    Returns:
        The first changed route that changed a shared family, or None.
    """
    shared = {
        family
        for route, entry in manifest["pages"].items()
        if route not in miss_routes
        for family in _claims_by_family(entry["dynamic_claims"])
    }
    changes = [
        (
            route,
            manifest["pages"].get(route, {}).get("dynamic_claims", []),
            _dynamic_claims(miss_ctx.stateful_routes.get(route, ()))
            if miss_ctx is not None
            else [],
        )
        for route in miss_routes
    ]
    changes.extend(
        (route, entry["dynamic_claims"], []) for route, entry in removed_entries.items()
    )
    for route, recorded_claims, live_claims in changes:
        recorded = _claims_by_family(recorded_claims)
        live = _claims_by_family(live_claims)
        if any(
            live.get(family) != recorded.get(family)
            for family in (live.keys() | recorded.keys()) & shared
        ):
            return route
    return None


_INSTANCE_NUMBER = re.compile(r"_n(\d+)$")


def _numbers_before_miss_pages(
    pages: Sequence[PageDefinition], manifest: dict[str, Any], miss_routes: set[str]
) -> dict[str, dict[str, int]]:
    """The highest ``ComponentState`` numbers kept pages drew before each miss.

    Args:
        pages: All current page definitions (in compile order).
        manifest: The loaded manifest.
        miss_routes: Routes re-evaluated in this rebuild.

    Returns:
        For each re-evaluated route, the dotted ``ComponentState`` class path
        mapped to the highest instance number drawn by an earlier kept page.
    """
    numbers: dict[str, int] = {}
    before: dict[str, dict[str, int]] = {}
    for page in pages:
        if page.route in miss_routes:
            if numbers:
                before[page.route] = dict(numbers)
            continue
        # A ComponentState claim requests its dotted class path; a local
        # state's request is a bare class name.
        for name, requested in manifest["pages"][page.route]["dynamic_claims"]:
            if "." in requested and (match := _INSTANCE_NUMBER.search(name)):
                numbers[requested] = max(numbers.get(requested, 0), int(match[1]))
    return before


def _resolve_class_path(path: str) -> Any:
    """Look up a loaded class by its dotted ``module.qualname`` path.

    Args:
        path: The dotted path.

    Returns:
        The object at the path, or None.
    """
    parts = path.split(".")
    for split in range(len(parts) - 1, 0, -1):
        if (obj := sys.modules.get(".".join(parts[:split]))) is not None:
            for part in parts[split:]:
                obj = getattr(obj, part, None)
            return obj
    return None


@dataclasses.dataclass(frozen=True, slots=True)
class _ComponentStateNumbersPlugin(Plugin):
    """Advance ``ComponentState`` counters before each re-evaluated page.

    Instance numbers are handed out in page order and only grow. Before a
    re-evaluated page, a full compile's counter is past every number drawn
    by the earlier pages: the kept ones (recorded) and the re-evaluated ones
    (drawn live in this rebuild).
    """

    numbers_before: dict[str, dict[str, int]]

    def eval_page(
        self, page_fn: Any, /, *, page: PageDefinition, **kwargs: Any
    ) -> None:
        """Advance the counters to the numbers kept pages drew before this page.

        Args:
            page_fn: The page function (unused).
            page: The page about to be evaluated.
            kwargs: Other hook arguments (unused).
        """
        from reflex.state import ComponentState

        for path, number in self.numbers_before.get(page.route, {}).items():
            cls = _resolve_class_path(path)
            if (
                isinstance(cls, type)
                and issubclass(cls, ComponentState)
                and cls._per_component_state_instance_count < number
            ):
                cls._per_component_state_instance_count = number


def _claim_recorded_dynamic_names(
    manifest: dict[str, Any], miss_routes: set[str]
) -> None:
    """Reserve the dynamic state names of the pages that are not re-evaluated.

    A local state takes the first free name for its class name, so with these
    reserved a re-evaluated page takes the suffix it has in a full compile
    whenever its own claims are unchanged.

    Args:
        manifest: The loaded manifest.
        miss_routes: Routes re-evaluated in this rebuild.
    """
    import reflex.istate.dynamic as istate_dynamic

    for route, entry in manifest["pages"].items():
        if route in miss_routes:
            continue
        for name, _ in entry["dynamic_claims"]:
            if not hasattr(istate_dynamic, name):
                setattr(istate_dynamic, name, None)


def _fall_back_after_evaluation(reason: str) -> None:
    """Fall back after pages were evaluated, or fail a prediction.

    Args:
        reason: Why the rebuild falls back.

    Raises:
        DynamicStatePredictionError: While predicting dynamic state names,
            where the fallback would evaluate pages out of page order.
    """
    if _predict_dynamic_names:
        raise DynamicStatePredictionError(reason)
    _log_fallback(reason)


def _with_dynamic_state_pages(
    miss_pages: list[PageDefinition],
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    *,
    removed: bool = False,
) -> list[PageDefinition]:
    """Expand a miss set with every page that defines dynamic-module states.

    States defined in ``reflex.istate.dynamic`` (function-local classes,
    ``ComponentState`` instances) take collision-suffixed names in evaluation
    order. Evaluating all of them in page order reproduces the names of a full
    compile and of the backend, which evaluates every stateful page. This is
    the exact rule; a compile that can retry in a fresh process predicts the
    names instead (see :func:`set_dynamic_name_prediction`).

    Args:
        miss_pages: The pages to recompile.
        pages: All current page definitions (in compile order).
        manifest: The loaded manifest.
        removed: Whether a removed page defined dynamic-module states.

    Returns:
        The expanded miss list, in ``pages`` order.
    """
    if not miss_pages and not removed:
        return miss_pages
    miss_routes = {page.route for page in miss_pages}
    return [
        page
        for page in pages
        if page.route in miss_routes or manifest["pages"][page.route]["dynamic_claims"]
    ]


def _changed_dependency_files(
    manifest: dict[str, Any],
    validator: page_cache.FileValidator,
    changed_hint: set[str] | None = None,
) -> set[str]:
    """Return every recorded dependency file whose content changed.

    Args:
        manifest: The loaded manifest.
        validator: The file validator bound to the manifest's file table.
        changed_hint: Resolved paths the watcher saw change, or None if unknown.

    Returns:
        The set of changed dependency file paths (a changed function slice
        as its file).
    """
    candidates: Iterable[str] = {
        path for entry in manifest["pages"].values() for path in entry["deps"]
    }
    if changed_hint is not None:
        candidates = changed_hint.intersection(candidates)
    return {page_cache.dep_file(path) for path in candidates if validator.changed(path)}


def _module_source_file(module_name: str | None) -> str | None:
    """Resolve a loaded module's source file path.

    Args:
        module_name: The dotted module name.

    Returns:
        The resolved file path string, or None.
    """
    file = getattr(sys.modules.get(module_name or ""), "__file__", None)
    if not file:
        return None
    try:
        return str(Path(file).resolve())
    except OSError:
        return None


def _memo_output_path(source_module: str | None) -> str | None:
    """Resolve the mirrored output file path for a memo source module.

    Args:
        source_module: The dotted module name that defined the memo.

    Returns:
        The absolute output path string, or None when the module can't be
        mirrored (unmirrored memos compile to one file per memo instead).
    """
    from reflex_base.utils import memo_paths

    from reflex.compiler import utils as compiler_utils

    segments = memo_paths.module_to_mirrored_segments(source_module)
    if segments is None:
        return None
    return compiler_utils.get_memo_module_path(segments)


def _memo_state_entries(
    hasher: Callable[[str], page_cache.FileEntry | None],
    files: dict[str, page_cache.FileEntry],
    root: Path | None,
    include_owner: Callable[[str | None], bool],
) -> dict[str, dict[str, Any]]:
    """Describe the user-memo output files the current registry demands.

    For each mirrored memo output file: the definitions landing in it, the
    source module's first-party import closure (as file-table paths), and the
    route owning the definitions (see ``registration_owner``) — None for memos
    registered at module import. Import-owned entries are a pure function of
    app import, so any process can compare them pre-evaluation; route-owned
    entries only exist after their owner page evaluates, so they are compared
    post-evaluation for recompiled routes and validated by their owner's
    hit/miss status otherwise. Memos without a resolvable module file (exec'd
    docs demos in synthetic modules) are excluded — they have no file to
    track and are covered by the ``changed_files`` net in
    :func:`_memo_defs_for_rewrite`.

    Args:
        hasher: A memoized path -> :func:`page_cache.file_entry` function.
        files: File table extended with the closures' entries. Kept separate
            from the manifest's own table until the rebuild has finished
            validating against it (see :func:`_update_manifest_for_misses`).
        root: Project root for the import-graph walk. None defaults to cwd.
        include_owner: Predicate over a definition's ``owner_route`` deciding
            which registry slice to describe.

    Returns:
        A JSON-able mapping of output path ->
        ``def_keys``/``deps``/``owner_route``.
    """
    from reflex_base.components.memo import MEMOS

    state: dict[str, dict[str, Any]] = {}
    for (name, source_module), definition in MEMOS.items():
        if not include_owner(definition.owner_route):
            continue
        path = _memo_output_path(source_module)
        if path is None:
            continue
        entry = state.get(path)
        if entry is None:
            module_file = _module_source_file(source_module)
            if module_file is None:
                continue
            deps: list[str] = []
            for dep in sorted(page_cache.module_py_dependencies(module_file, root)):
                dep_entry = hasher(dep)
                if dep_entry is not None:
                    files[dep] = dep_entry
                    deps.append(dep)
            entry = state[path] = {
                "def_keys": [],
                "deps": deps,
                "owner_route": definition.owner_route,
            }
        entry["def_keys"].append([name, source_module])
    for entry in state.values():
        entry["def_keys"].sort()
    return state


def _memo_deps_changed(
    deps: Sequence[str],
    validator: page_cache.FileValidator,
    changed_hint: set[str] | None,
) -> bool:
    """Whether any file in a memo record's import closure changed.

    Args:
        deps: The record's dependency paths.
        validator: The file validator bound to the manifest's file table.
        changed_hint: Resolved paths the watcher saw change, or None if unknown.

    Returns:
        True if a dependency's content changed since it was recorded.
    """
    if changed_hint is not None and changed_hint.isdisjoint(deps):
        return False
    return not validator.unchanged(deps)


def _dirty_memo_paths(
    state: dict[str, dict[str, Any]],
    stored: dict[str, dict[str, Any]],
    validator: page_cache.FileValidator,
    changed_hint: set[str] | None,
) -> set[str]:
    """Return the demanded memo output files whose stored record is stale.

    A record is stale when the registry's demand differs from what was stored
    (a new or removed memo module, or a moved definition) or when a file in
    its import closure changed (an edited memo body or helper).

    Args:
        state: The memo records the current registry demands.
        stored: The manifest's memo records.
        validator: The file validator bound to the manifest's file table.
        changed_hint: Resolved paths the watcher saw change, or None if unknown.

    Returns:
        The output paths to rewrite.
    """
    return {
        path
        for path, entry in state.items()
        if stored.get(path) != entry
        or _memo_deps_changed(entry["deps"], validator, changed_hint)
    }


def _memo_defs_for_rewrite(
    contributions: dict[tuple[str, str | None], Any],
    dirty_paths: set[str],
    changed_files: set[str],
) -> list[Any]:
    """Return the full definition set for the memo files being rewritten.

    Memo output is grouped one file per source module, so a rewrite must carry
    every definition landing in that file: the recompiled pages' auto-memo
    contributions plus every user ``@rx.memo`` definition whose output file is
    being rewritten — because its recorded memo state changed (``dirty_paths``,
    see :func:`_current_memo_state`) or because a recompiled page contributes
    auto memos to it. The ``changed_files`` condition runs post-evaluation, so
    it additionally covers memos the pre-evaluation state can't see: modules
    imported inside a page function whose file (a recorded page dependency)
    changed.

    Args:
        contributions: The recompiled pages' auto-memo contributions.
        dirty_paths: Output paths whose stored memo state no longer matches.
        changed_files: The recorded dependency files whose content changed.

    Returns:
        The memo definitions to compile, user memos first (matching the full
        compile's emit order).
    """
    from reflex_base.components.memo import MEMOS

    rewrite_paths = dirty_paths | {
        path
        for definition in contributions.values()
        if (path := _memo_output_path(definition.source_module)) is not None
    }
    user_memos = [
        memo
        for (_, source_module), memo in MEMOS.items()
        if _memo_output_path(source_module) in rewrite_paths
        or _module_source_file(source_module) in changed_files
    ]
    return [*user_memos, *contributions.values()]


def _with_memo_contributing_pages(
    miss_pages: list[PageDefinition],
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    dirty_paths: set[str],
    stale_owner_routes: set[str],
) -> list[PageDefinition]:
    """Add hit pages that must re-evaluate for a memo file rewrite.

    A dirty user-memo file is rewritten from scratch, so hit pages
    contributing auto memos to the same file must be re-evaluated for their
    contributions, or the rewrite would drop their exports. Likewise, a
    route-owned memo entry whose dependency files changed needs its owner
    page re-evaluated: only that page's evaluation re-registers the memo
    definitions the rewrite compiles from.

    Args:
        miss_pages: The dependency-changed pages.
        pages: All current page definitions (in compile order).
        manifest: The loaded manifest.
        dirty_paths: Output paths whose stored memo state no longer matches.
        stale_owner_routes: Routes owning stored memo entries with changed
            dependency files.

    Returns:
        The miss list extended with the affected hit pages.
    """
    miss_routes = {page.route for page in miss_pages}
    extra = [
        page
        for page in pages
        if page.route not in miss_routes
        and (
            page.route in stale_owner_routes
            or (
                manifest["pages"][page.route]["has_memos"]
                and _memo_output_path(getattr(page, "_source_module", None))
                in dirty_paths
            )
        )
    ]
    return [*miss_pages, *extra] if extra else miss_pages


def _refresh_file_table(
    manifest: dict[str, Any], validator: page_cache.FileValidator
) -> bool:
    """Fold touched-but-identical files' fresh stat keys into the manifest.

    Args:
        manifest: The loaded manifest (mutated).
        validator: The validator whose ``refreshed`` entries to apply.

    Returns:
        True if any entry was updated.
    """
    if not validator.refreshed:
        return False
    manifest["files"].update(validator.refreshed)
    return True


def _save_incremental_output(
    path: str, code: str, outputs: dict[Path, str] | None
) -> None:
    """Stage output for plugin processing or write it for a direct rebuild.

    Args:
        path: Generated path relative to the web directory.
        code: Generated file content.
        outputs: Output mapping supplied by the main compiler, if any.
    """
    from reflex.compiler import utils as compiler_utils

    resolved = compiler_utils.resolve_path_of_web_dir(path)
    if outputs is None:
        compiler_utils.write_file(resolved, code)
    else:
        outputs[resolved] = code


def try_incremental_rebuild(
    app: App,
    *,
    compiler_plugins: Any,
    prerender_routes: bool,
    root: Path | None = None,
    use_rich: bool = True,
    outputs: dict[Path, str] | None = None,
    registrations: dict[str, str] | None = None,
) -> bool | CompileContext:
    """Attempt a disk-cache-assisted partial rebuild; report whether it ran.

    Returns False (so the caller does a full compile) whenever anything is
    unsafe to reuse: no/old manifest, a changed global input or a route change.
    When a miss page turns out to have altered its app-wrap set or stateful
    flag, the miss pages are already evaluated and rendered. A page is never
    evaluated twice in one process (its locally defined states would register
    under collision-suffixed names the backend does not use), so the context
    holding those compiled pages is returned instead of False, for the full
    compile to adopt (see ``CompileContext.absorb``).

    User-memo output files are reconciled against the manifest's stored memo
    record (see :func:`_current_memo_state`): files whose record differs are
    rewritten, with the affected memo-contributing hit pages re-evaluated so
    their exports survive the rewrite. Files of deleted memo modules are left
    orphaned (nothing imports them; the next full compile prunes them).

    The ``assets`` copy is excluded from dependency tracking and always re-run
    (cheap, idempotent). The contexts file is rewritten only when a stateful
    miss changed its state config, and then from this process's state tree
    plus the manifest's stored contributions of the stateful hit pages, so no
    unchanged page is ever re-evaluated.

    On success, reports (at info level) how many pages were recompiled vs reused
    and, while recompiling, shows a progress bar over the changed pages so a hot
    reload makes the incremental work visible.

    Args:
        app: The app being compiled.
        compiler_plugins: The resolved compiler plugins for this compile.
        prerender_routes: Whether to prerender routes.
        root: Project root for fingerprinting. Defaults to cwd.
        use_rich: Whether to use a rich progress bar (else a plain fallback).
        outputs: Stage generated files here for plugin processing instead of writing.
        registrations: Each route's registration digest, taken before any page
            evaluated; computed now when absent.

    Returns:
        True if the partial rebuild completed (the caller should return), False
        for a full compile, or the context of the pages already compiled here
        for a full compile that adopts them.
    """
    manifest = load_manifest()
    if manifest is None:
        _log_fallback(
            "no reusable manifest (first compile, unreadable, or schema changed)"
        )
        return False

    pages = list(app._unevaluated_pages.values())
    routes = {p.route for p in pages}
    if registrations is None:
        registrations = registration_digests(pages)
    validator = page_cache.FileValidator(manifest["files"])
    changed_hint = _with_hinted_slices(_changed_hint, manifest)

    if (
        reason := globals_mismatch(manifest, validator=validator, root=root)
    ) is not None:
        _log_fallback(reason)
        return False

    resolved_root = (root or Path.cwd()).resolve()
    # Removed routes leave the manifest; added ones have no entry, so they miss.
    removed_entries = {
        route: manifest["pages"].pop(route)
        for route in [route for route in manifest["pages"] if route not in routes]
    }
    route_set_changed = bool(removed_entries) or not routes <= set(manifest["pages"])
    # The states importing the app registered (no page has evaluated yet).
    page_states = {
        name
        for entry in (*manifest["pages"].values(), *removed_entries.values())
        if (state_slice := entry["state_slice"])
        for name in state_slice["schema"]
    }
    live_module_states = [
        name
        for name in RegistrationContext.ensure_context().base_states
        if name not in page_states
    ]
    recorded_module_states = manifest["module_states"]
    module_states_changed = sorted(live_module_states) != recorded_module_states[
        "names"
    ] or not (
        (
            changed_hint is not None
            and changed_hint.isdisjoint(recorded_module_states["files"])
        )
        or validator.unchanged(recorded_module_states["files"])
    )
    if module_states_changed:
        import reflex.istate.dynamic as istate_dynamic

        base_states = RegistrationContext.ensure_context().base_states
        if sorted(
            name
            for name in live_module_states
            if base_states[name].__module__ == istate_dynamic.__name__
        ) != sorted(recorded_module_states["dynamic"]):
            # They take names before any page, so every page's could shift.
            _log_fallback("the app's import-time dynamic states changed")
            return False
    miss_pages = partition_pages(
        pages, manifest, validator, changed_hint, registrations
    )
    # Memo files are decided salsa-style: derive the files the current memo
    # registry demands and rewrite the ones whose stored record differs. This
    # catches what changed-file diffing structurally cannot: a memo module the
    # previous compile never saw (its file is in no recorded dependency set).
    # Only import-owned memos are comparable here (pre-evaluation);
    # route-owned entries are handled by owner status: a changed dependency
    # pulls the owner page into the miss set, and its re-evaluation feeds the
    # post-evaluation comparison below.
    memo_hasher = page_cache.make_hasher()
    memo_files_table: dict[str, page_cache.FileEntry] = {}
    memo_state = _memo_state_entries(
        memo_hasher, memo_files_table, resolved_root, lambda owner: owner is None
    )
    stored_memo_files = manifest["memo_files"]
    dirty_memo_paths = _dirty_memo_paths(
        memo_state, stored_memo_files, validator, changed_hint
    )
    # A removed page's auto memos must leave its module's memo file.
    removed_memo_paths = {
        path for entry in removed_entries.values() if (path := entry["memo_path"])
    }
    dirty_memo_paths |= removed_memo_paths
    stale_owner_routes = {
        owner
        for entry in stored_memo_files.values()
        if (owner := entry["owner_route"]) is not None
        and owner in routes
        and _memo_deps_changed(entry["deps"], validator, changed_hint)
    }
    changed_files: set[str] = set()
    if miss_pages or dirty_memo_paths or stale_owner_routes or removed_entries:
        changed_files = _changed_dependency_files(manifest, validator, changed_hint)
        miss_pages = _with_memo_contributing_pages(
            miss_pages, pages, manifest, dirty_memo_paths, stale_owner_routes
        )
        miss_pages = _with_module_siblings(miss_pages, pages, manifest)
        if not _predict_dynamic_names:
            miss_pages = _with_dynamic_state_pages(
                miss_pages,
                pages,
                manifest,
                removed=any(e["dynamic_claims"] for e in removed_entries.values()),
            )
        memo_note = (
            f"; rewriting {len(dirty_memo_paths)} memo file(s)"
            if dirty_memo_paths
            else ""
        )
        logger.info(
            f"Compile cache: recompiling {len(miss_pages)}/{len(pages)} pages; "
            f"changed file(s): {format_path_list(changed_files, resolved_root)}"
            f"{memo_note}"
        )
    else:
        logger.info(f"Compile cache: reusing all {len(pages)} pages from disk")
    miss_routes = {p.route for p in miss_pages}

    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    bundle_base: list[str] = []
    if miss_pages or dirty_memo_paths or route_set_changed:
        # Match the full compile's clean bundling/memo state before compiling.
        bundle_base = compiler._reset_compile_registries(compiler_plugins)

    # Recompile only the source-changed pages.
    miss_ctx = None
    if miss_pages:
        # Page evaluation can import modules the cached import graph (built
        # pre-evaluation for the memo state) has never seen; drop the cache
        # afterwards so post-evaluation closures (memo entries, page deps)
        # include the newly loaded modules.
        modules_before = set(page_cache._loaded_first_party_modules(resolved_root))
        page_plugins: Sequence[Plugin] = compiler_plugins
        if _predict_dynamic_names:
            _claim_recorded_dynamic_names(manifest, miss_routes)
            page_plugins = (
                _ComponentStateNumbersPlugin(
                    _numbers_before_miss_pages(pages, manifest, miss_routes)
                ),
                *compiler_plugins,
            )

        miss_ctx = CompileContext(
            app=app,
            pages=miss_pages,
            hooks=CompilerHooks(
                plugins=default_page_plugins(style=app.style, plugins=page_plugins)
            ),
            bundle_base=bundle_base,
        )
        # Progress over the changed pages (evaluate + render each), so a hot
        # reload shows how much is being recompiled.
        progress = console.progress() if use_rich else console.PoorProgress()
        progress.start()
        task = progress.add_task(
            "Recompiling changed pages:", total=len(miss_pages) * 2
        )
        try:
            with miss_ctx:
                miss_ctx.compile(
                    evaluate_progress=lambda: progress.advance(task),
                    render_progress=lambda: progress.advance(task),
                )
        finally:
            progress.stop()
        if set(page_cache._loaded_first_party_modules(resolved_root)) != modules_before:
            page_cache.clear_import_graph()
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                _fall_back_after_evaluation(f"page {page.route!r} produced no output")
                return False

    if _predict_dynamic_names and (
        route := _shifting_dynamic_claims(
            manifest, miss_ctx, miss_routes, removed_entries
        )
    ):
        _fall_back_after_evaluation(
            f"page {route!r} changed dynamic state names other pages share"
        )

    # Write changed pages + their memo files; reuse everything else on disk.
    install_imports = _deserialize_imports(manifest["all_imports"])
    eval_memo_state: dict[str, dict[str, Any]] = {}
    # Outputs of removed pages, deleted once the rebuild succeeded.
    stale_outputs = [compiler_utils.get_page_path(route) for route in removed_entries]
    if miss_ctx is not None or dirty_memo_paths:
        memo_contributions: dict[tuple[str, str | None], Any] = {}
        miss_imports = []
        if miss_ctx is not None:
            for page in miss_pages:
                page_ctx = miss_ctx.compiled_pages[page.route]
                # Both are guaranteed non-None by the guard loop above.
                output_path = page_ctx.output_path
                output_code = page_ctx.output_code
                if output_path is None or output_code is None:
                    _fall_back_after_evaluation(
                        f"page {page.route!r} lost its output before write"
                    )
                    return False
                _save_incremental_output(output_path, output_code, outputs)
                memo_contributions.update(page_ctx.memo_contributions)
                miss_imports.append(page_ctx.frontend_imports)
            # Post-evaluation pass: the miss pages just evaluated, so memos
            # they own (registered during their evaluation, e.g. from modules
            # imported inside the page function) are now in the registry.
            # A brand-new such module has no stored record and must be
            # written; an unchanged one matches its record and is skipped.
            eval_memo_state = _memo_state_entries(
                memo_hasher,
                memo_files_table,
                resolved_root,
                lambda owner: owner in miss_routes,
            )
            dirty_memo_paths = dirty_memo_paths | _dirty_memo_paths(
                eval_memo_state, stored_memo_files, validator, changed_hint
            )
        # Memo output files are grouped per source module, so compile them once
        # with the complete definition set (all recompiled pages' contributions
        # plus the user memos landing in a file being rewritten).
        memo_files, memo_imports = compiler.compile_memo_components(
            _memo_defs_for_rewrite(memo_contributions, dirty_memo_paths, changed_files)
        )
        for mpath, mcode in memo_files:
            _save_incremental_output(mpath, mcode, outputs)
        emitted = {mpath for mpath, _ in memo_files}
        stale_outputs.extend(
            path
            for path in removed_memo_paths
            if path not in emitted and path not in manifest["memo_files"]
        )
        # Merge once: re-merging the app-wide set per page re-walks its ~100k
        # entries each time.
        install_imports = merge_imports(install_imports, *miss_imports, memo_imports)

    # Record which routes are stateful: miss pages from this compile, hit pages
    # from the manifest, so the stateful-pages marker is complete. We do NOT
    # re-evaluate hit pages to register their state in this process: it only
    # produces .web and exits (the daemon, the initial compile, and CLI compiles
    # never serve), and the serving backend re-evaluates the marked stateful
    # pages itself.
    stateful_routes: dict[str, None] = {}
    for page in pages:
        if page.route in miss_routes:
            if miss_ctx is not None and page.route in miss_ctx.stateful_routes:
                stateful_routes[page.route] = None
        elif manifest["pages"][page.route]["is_stateful"]:
            stateful_routes[page.route] = None

    if miss_ctx is not None:
        compiler._register_compiled_pages(app, miss_ctx.compiled_pages)

    app._stateful_pages.update(stateful_routes)
    app._write_stateful_pages_marker()
    app._add_optional_endpoints()
    app._validate_var_dependencies()

    # The contexts file holds EVERY state's defaults/dispatchers, including
    # states only registered while their page evaluates (exec'd docs demos,
    # dynamically imported modules). This process evaluated just the miss
    # pages, so its state tree lacks the hit pages' page-registered states;
    # their contributions come from the manifest instead (``state_slice``),
    # so rebuilding contexts never re-evaluates an unchanged page. Only a
    # stateful miss can change state config, and only its OWN states can differ
    # from the on-disk contexts file, so compare those first: a content-only
    # edit leaves them identical and the contexts file is reused untouched.
    contexts_snapshot: compiler_utils.ContextsSnapshot | None = None
    state_libraries: dict[str, list[str]] = manifest["state_libraries"]
    if (
        route_set_changed
        or module_states_changed
        or (
            miss_ctx is not None
            and any(
                route in miss_ctx.stateful_routes
                or manifest["pages"].get(route, {}).get("is_stateful")
                for route in miss_routes
            )
        )
    ):
        contexts_snapshot = _contexts_snapshot(app)
        # A route change can drop slices or add dynamic route arguments to the
        # root state, so it always rebuilds the contexts.
        changed_route = (
            "the route set"
            if route_set_changed
            else "the app's states"
            if module_states_changed
            else _changed_state_config_route(
                manifest, miss_ctx, contexts_snapshot, miss_routes
            )
            if miss_ctx is not None
            else None
        )
        if changed_route is None:
            logger.info(
                "Compile cache: recompiled pages define unchanged states; "
                "reusing contexts file"
            )
        else:
            logger.info(
                f"Compile cache: {changed_route!r} changed the state config; "
                "rebuilding contexts"
            )
            from reflex_components_radix.plugin import RadixThemesPlugin

            theme = next(
                (
                    plugin.get_theme()
                    for plugin in compiler_plugins
                    if isinstance(plugin, RadixThemesPlugin)
                ),
                None,
            )
            merged_snapshot = (
                None
                if contexts_snapshot is None
                else _with_hit_state_slices(contexts_snapshot, manifest, miss_routes)
            )
            context_path, context_code = compiler.compile_contexts(
                app._state, theme, contexts_snapshot=merged_snapshot
            )
            _save_incremental_output(context_path, context_code, outputs)
            if contexts_snapshot is not None and merged_snapshot is not None:
                live_libraries = _state_libraries(contexts_snapshot[0])
                state_libraries = {
                    name: libraries
                    for name in merged_snapshot[0]
                    if (
                        libraries := live_libraries.get(name)
                        if name in contexts_snapshot[0]
                        else state_libraries.get(name)
                    )
                }

    app_root_inputs = manifest["app_root"]
    if miss_ctx is not None or route_set_changed:
        try:
            refreshed = _refresh_app_root(
                app,
                manifest,
                pages,
                miss_ctx.compiled_pages if miss_ctx is not None else {},
                bundle_base,
                state_libraries,
                outputs,
            )
        except _AppRootUnavailableError as err:
            _fall_back_after_evaluation(str(err))
            return miss_ctx if miss_ctx is not None else False
        if refreshed is not None:
            app_root_inputs, root_imports = refreshed
            install_imports = merge_imports(install_imports, root_imports)

    # The assets copy is cheap, idempotent, and excluded from dependency
    # tracking entirely, so it is always re-run.
    assets_src = (root or Path.cwd()) / constants.Dirs.APP_ASSETS
    if assets_src.is_dir():
        path_ops.update_directory_tree(
            src=assets_src,
            dest=prerequisites.get_web_dir() / constants.Dirs.PUBLIC,
        )

    # Frontend packages + routing scaffolding (cheap, idempotent).
    from reflex.utils import frontend_skeleton

    with log.timing(logger, "Install Frontend Packages"):
        app._get_frontend_packages(install_imports)
    frontend_skeleton.update_react_router_config(prerender_routes=prerender_routes)
    frontend_skeleton.update_entry_client()
    frontend_skeleton.initialize_vite_config()

    # The next manifest merges three memo-record sources, mirroring salsa's
    # reuse of queries that did not re-run: route-owned entries whose owner
    # page hit carry forward unchanged (their page never re-evaluated here),
    # import-owned entries are recomputed from the pre-evaluation registry,
    # and entries owned by the recompiled routes are recomputed post-eval.
    final_memo_state = {
        **{
            path: entry
            for path, entry in stored_memo_files.items()
            if entry["owner_route"] is not None
            and entry["owner_route"] not in miss_routes
            and entry["owner_route"] in routes
        },
        **memo_state,
        **eval_memo_state,
    }

    # Refresh the manifest for the next process.
    _update_manifest_for_misses(
        manifest,
        miss_ctx,
        miss_pages,
        install_imports,
        root,
        contexts_snapshot=contexts_snapshot,
        memo_state=final_memo_state,
        memo_file_entries=memo_files_table,
        app_root_inputs=app_root_inputs,
        state_libraries=state_libraries,
        registrations=registrations,
        module_states=(
            _record_module_states(
                live_module_states,
                page_cache.make_hasher(),
                manifest["files"],
                root,
            )
            if module_states_changed
            else recorded_module_states
        ),
        route_set_changed=route_set_changed,
        validator=validator,
    )

    # The route table the production static server reads.
    _save_incremental_output(
        constants.Dirs.ROUTES_MANIFEST, json.dumps(app._page_routes), outputs
    )
    for path in stale_outputs:
        Path(path).unlink(missing_ok=True)

    counts: dict[str, int] = {}
    for page in pages:
        page_counts = manifest["pages"][page.route].get("component_counts", {})
        for name, count in page_counts.items():
            counts[name] = counts.get(name, 0) + count
    app._cached_component_counts = counts
    return True


class _AppRootUnavailableError(Exception):
    """The app root cannot be rebuilt from the recorded inputs."""


def _refresh_app_root(
    app: App,
    manifest: dict[str, Any],
    pages: Sequence[PageDefinition],
    compiled_pages: dict[str, PageContext],
    bundle_base: Sequence[str],
    state_libraries: dict[str, list[str]],
    outputs: dict[Path, str] | None,
) -> tuple[dict[str, Any], ParsedImportDict] | None:
    """Rebuild the app root and bundled-library file when their inputs changed.

    The app root is a function of the pages' merged app wraps (positioned by
    the first page requiring each, valued by the last, like the full compile's
    ``dict.update``) and of the bundled libraries, rebuilt in full-compile
    order from each page's and state's recorded requests. When neither
    changed, the root on disk stays. Otherwise it is rebuilt from the
    recompiled pages' live wraps and the recorded wraps of the other pages,
    without evaluating them.

    Args:
        app: The app being compiled.
        manifest: The loaded manifest; its wrap table gains the live wraps.
        pages: All current page definitions (in compile order).
        compiled_pages: The recompiled pages' contexts, by route.
        bundle_base: The bundled libraries registered after this rebuild's
            registry reset.
        state_libraries: The libraries each state's initial values request.
        outputs: Output mapping supplied by the main compiler, if any.

    Returns:
        The new recorded app-root inputs and the imports the root needs, or
        None when the root is unchanged.

    Raises:
        _AppRootUnavailableError: When the recorded inputs cannot rebuild it.
    """
    from reflex_base.components.memo import MEMOS

    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    stored = manifest["app_root"]
    wrap_table = manifest["wrap_table"]
    merged: dict[str, str] = {}
    providers: dict[str, str] = {}
    page_requests = []
    memo_paths: set[str] = set(manifest["memo_files"])
    for page in pages:
        if (page_ctx := compiled_pages.get(page.route)) is not None:
            wraps = _record_app_wraps(page_ctx, wrap_table)
            page_requests.append([
                page_ctx.evaluate_bundle_requests,
                page_ctx.render_bundle_requests,
            ])
            has_memos = bool(page_ctx.memo_contributions)
        else:
            entry = manifest["pages"][page.route]
            wraps = entry["app_wraps"]
            page_requests.append(entry["bundle_requests"])
            has_memos = entry["has_memos"]
        if has_memos and (
            path := _memo_output_path(getattr(page, "_source_module", None))
        ):
            memo_paths.add(path)
        for key_str, digest in wraps.items():
            merged[key_str] = digest
            providers[key_str] = page.route
    libraries = _reconstruct_libraries(
        bundle_base, page_requests, stored["root_requests"], state_libraries
    )
    if merged == stored["wraps"] and libraries == stored["libraries"]:
        return None
    if not stored["reconstructible"]:
        msg = "the app root's bundled libraries cannot be rebuilt"
        raise _AppRootUnavailableError(msg)

    components = {}
    for key_str, digest in merged.items():
        key = _wrap_key(key_str)
        if (page_ctx := compiled_pages.get(providers[key_str])) is not None:
            components[key] = page_ctx.app_wrap_components[key]
        elif (data := wrap_table.get(digest)) is not None:
            components[key] = pickle.loads(base64.b64decode(data))
        else:
            msg = f"page {providers[key_str]!r} requires an app wrap that cannot be stored"
            raise _AppRootUnavailableError(msg)
    logger.info(
        "Compile cache: the app wraps or bundled libraries changed; rebuilding the app root"
    )
    memos_before = set(MEMOS)
    root_ctx = CompileContext(app=app, pages=())
    with root_ctx, record_bundle_requests() as root_requests:
        app_root, hydrate_fallback_export = compiler._build_app_root(
            app, components, root_ctx
        )
    root_memos = [
        *(memo for key, memo in MEMOS.items() if key not in memos_before),
        *root_ctx.auto_memo_components.values(),
    ]
    root_memo_paths = {
        path
        for memo in root_memos
        if (path := _memo_output_path(memo.source_module)) is not None
    }
    if root_memo_paths & memo_paths:
        msg = "the app root's memos share a file with page memos"
        raise _AppRootUnavailableError(msg)
    memo_files, memo_imports = compiler.compile_memo_components([
        *(
            memo
            for key, memo in MEMOS.items()
            if key in memos_before and _memo_output_path(key[1]) in root_memo_paths
        ),
        *root_memos,
    ])
    libraries = _reconstruct_libraries(
        bundle_base, page_requests, root_requests, state_libraries
    )
    RegistrationContext.ensure_context().bundled_libraries[:] = libraries
    for path, code in (
        *memo_files,
        compiler.compile_app_root(app_root, hydrate_fallback_export),
        compiler_utils._compile_bundled_libraries(),
    ):
        _save_incremental_output(path, code, outputs)
    return (
        {
            "wraps": merged,
            "libraries": libraries,
            "root_requests": root_requests,
            "reconstructible": True,
        },
        merge_imports(app_root._get_all_imports(), memo_imports),
    )


def _update_manifest_for_misses(
    manifest: dict[str, Any],
    miss_ctx: CompileContext | None,
    miss_pages: Sequence[PageDefinition],
    all_imports: ParsedImportDict,
    root: Path | None = None,
    *,
    contexts_snapshot: compiler_utils.ContextsSnapshot | None = None,
    memo_state: dict[str, dict[str, Any]],
    memo_file_entries: dict[str, page_cache.FileEntry],
    app_root_inputs: dict[str, Any],
    state_libraries: dict[str, list[str]],
    registrations: dict[str, str],
    module_states: dict[str, list[str]],
    route_set_changed: bool = False,
    validator: page_cache.FileValidator | None = None,
) -> None:
    """Update the on-disk manifest entries for the recompiled pages.

    Also refreshes the stat keys of files that were touched without changing
    (so they are not re-hashed on every later reload) and persists the
    import-name parse cache. Rewritten only when something changed.

    Args:
        manifest: The loaded manifest (mutated and rewritten).
        miss_ctx: The compile context of the recompiled pages, if any.
        miss_pages: The recompiled page definitions.
        all_imports: The complete frontend import set after this rebuild.
        root: Project root for dependency discovery. Defaults to cwd.
        contexts_snapshot: The app's ``_contexts_snapshot`` for slicing
            stateful pages, or None when no miss page was stateful.
        memo_state: The current user-memo file record to persist (see
            :func:`_memo_state_entries`).
        memo_file_entries: File-table entries for the memo records' closures,
            withheld until validation finished.
        app_root_inputs: The app root's recorded inputs after this rebuild.
        state_libraries: The libraries each state's initial values request.
        registrations: Each route's registration digest.
        module_states: The import-time states and their source files.
        route_set_changed: Whether pages were added or removed.
        validator: The validator used for this rebuild, for its refreshed
            entries.
    """
    try:
        dirty = route_set_changed or (
            validator is not None and _refresh_file_table(manifest, validator)
        )
        # An entry module whose edit only changed page registrations stays the
        # recorded one; record its new content so the next rebuild skips it.
        if (
            validator is not None
            and (entry_path := manifest["entry"]["path"]) is not None
            and validator.changed(entry_path)
            and (entry := page_cache.file_entry(entry_path)) is not None
        ):
            manifest["files"][entry_path] = list(entry)
            dirty = True
        if manifest["memo_files"] != memo_state:
            manifest["memo_files"] = memo_state
            manifest["files"].update(memo_file_entries)
            dirty = True
        if miss_ctx is not None and miss_pages:
            state_index, _ = page_cache.state_dependency_index(root)
            hasher = page_cache.make_hasher()
            for page in miss_pages:
                page_ctx = miss_ctx.compiled_pages[page.route]
                defined_states = miss_ctx.stateful_routes.get(page.route)
                manifest["pages"][page.route] = _manifest_page_entry(
                    page_ctx,
                    page,
                    state_index,
                    hasher,
                    manifest["files"],
                    defined_states=defined_states,
                    registration=registrations[page.route],
                    wrap_table=manifest["wrap_table"],
                    state_slice=(
                        _state_slice(defined_states, *contexts_snapshot)
                        if defined_states and contexts_snapshot is not None
                        else None
                    ),
                    root=root,
                )
            dirty = True
        if (
            manifest["app_root"] != app_root_inputs
            or manifest["state_libraries"] != state_libraries
            or manifest["module_states"] != module_states
        ):
            manifest["app_root"] = app_root_inputs
            manifest["state_libraries"] = state_libraries
            manifest["module_states"] = module_states
            dirty = True
        if dirty:
            # Keep only the stored wraps a page or the app root still uses.
            used = set(app_root_inputs["wraps"].values()).union(
                *(entry["app_wraps"].values() for entry in manifest["pages"].values())
            )
            manifest["wrap_table"] = {
                digest: data
                for digest, data in manifest["wrap_table"].items()
                if digest in used
            }
        # A memo-only rewrite can add packages with no page recompiled.
        if (imports := _serialize_imports(all_imports)) != manifest["all_imports"]:
            manifest["all_imports"] = imports
            dirty = True
        if dirty:
            _write(manifest)
    except Exception as exc:  # best-effort
        logger.warning(f"Compile cache: could not refresh manifest ({exc!r}).")
