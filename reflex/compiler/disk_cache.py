"""Disk-persisted incremental compile cache for ``REFLEX_COMPILE_CACHE``.

The manifest stores only bookkeeping: a file table (content hash plus stat key
per dependency file), each page's dependency paths, app-wrap digests, memo
uses, statefulness and its contribution to the contexts file, the app-wide
frontend imports, the app root's inputs, and the import-name parse cache.
Rendered files stay in ``.web``. When the global inputs, the page set and the
registrations still match, unchanged pages are reused from disk and only
dependency-changed pages are recompiled.

Each page is a memoized query over the inputs it recorded. Outputs that
several pages feed are handled in one of two ways: the memo files are
content-addressed, one file per auto memo, so a page's memos never share a
file with another page's; and the app root and the bundled-library file are
compared against their recorded inputs and fall back to a full compile when a
recompiled page changed them.

Validation is stat-first (see :class:`page_cache.FileValidator`): an unchanged
file is recognised from ``(mtime_ns, size)`` without being read, and when the
watcher reports which paths changed, pages depending on none of them are hits
without even a stat.
"""

from __future__ import annotations

import contextlib
import dataclasses
import functools
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base import constants
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
_SCHEMA = 23
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
#: that can discard this process and compile again sets it; None means no
#: caller chose, and a cold compile tries it in a forked child (see
#: ``compile_daemon.compiled_in_predicting_child``).
_predict_dynamic_names: bool | None = None


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
    """Return the manifest's path in the web directory.

    Returns:
        The manifest path.
    """
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


def _record_app_wraps(page_ctx: PageContext) -> dict[str, str]:
    """Record a page's app wraps by digest.

    Args:
        page_ctx: The compiled page context.

    Returns:
        The page's app-wrap keys mapped to their digests, in page order.
    """
    return {
        _wrap_key_str(key): _wrap_digest(component)
        for key, component in page_ctx.app_wrap_components.items()
    }


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
    if isinstance(value, functools.partial):
        return [
            _stable_value(value.func),
            _stable_value(value.args),
            _stable_value(value.keywords),
        ]
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


def _memo_keys(page_ctx: PageContext) -> list[str]:
    """The export names of the auto memos a page's output imports.

    Args:
        page_ctx: The compiled page context.

    Returns:
        The sorted memo tags.
    """
    return sorted(tag for tag, _ in page_ctx.memo_uses)


def _uses_radix(root_component: object) -> bool:
    """Whether a rendered tree holds a Radix Themes component.

    The implicit ``RadixThemesPlugin`` enables itself when it compiles one;
    a page reused from disk is not compiled, so the manifest remembers.

    Args:
        root_component: The page's root component.

    Returns:
        True when the tree enables Radix Themes.
    """
    from reflex_components_radix.themes.base import RadixThemesComponent

    return any(
        issubclass(cls, RadixThemesComponent)
        for cls in page_cache.component_tree_classes(root_component)
    )


def _manifest_page_entry(
    page_ctx: PageContext,
    page: PageDefinition,
    state_index: dict[str, Path],
    hasher: Callable[[str], page_cache.FileEntry | None],
    files: dict[str, page_cache.FileEntry],
    *,
    defined_states: Sequence[str] | None,
    registration: str,
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
        # Everything the page was registered with (see ``_pages_mismatch``).
        "registration": registration,
        # The app wraps the page requires, by digest (see ``_app_root_change``).
        "app_wraps": _record_app_wraps(page_ctx),
        "is_stateful": defined_states is not None,
        "state_slice": state_slice,
        # The ``reflex.istate.dynamic`` names the page's states took, whose
        # suffixes depend on evaluation order (see ``_with_dynamic_state_pages``).
        "dynamic_claims": _dynamic_claims(defined_states or ()),
        # The auto memos the page imports, each in its own content-addressed
        # file (see ``_memo_file``); the files a rebuild may drop are the ones
        # no page uses any more.
        "memo_keys": _memo_keys(page_ctx),
        # Whether the page enables the implicit Radix Themes plugin.
        "radix": _uses_radix(page_ctx.root_component),
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


def _hit_page_states(manifest: dict[str, Any], miss_routes: set[str]) -> set[str]:
    """The states the manifest records as defined by pages that hit.

    Args:
        manifest: The loaded manifest.
        miss_routes: The recompiled routes.

    Returns:
        The full names of the hit pages' states.
    """
    return {
        name
        for route, entry in manifest["pages"].items()
        if route not in miss_routes and (state_slice := entry["state_slice"])
        for name in state_slice["schema"]
    }


def _disown_hit_page_states(
    miss_ctx: CompileContext, manifest: dict[str, Any], miss_routes: set[str]
) -> None:
    """Leave a hit page's states to it when a recompiled page registers them.

    A module state is recorded by the page whose evaluation first imported
    its module. In a process that evaluates only the recompiled pages, one
    of them can import that module first and would otherwise claim the
    state, marking itself stateful where a full compile would not.

    Args:
        miss_ctx: The compile context of the recompiled pages (mutated).
        manifest: The loaded manifest.
        miss_routes: The recompiled routes.
    """
    owned = _hit_page_states(manifest, miss_routes)
    for route, names in list(miss_ctx.stateful_routes.items()):
        if kept := [name for name in names if name not in owned]:
            miss_ctx.stateful_routes[route] = kept
        else:
            del miss_ctx.stateful_routes[route]


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


def manifest_dependency_entries(manifest: dict[str, Any]) -> set[str]:
    """Every file-table key the manifest's current entries reference.

    An incremental rebuild extends the file table without pruning it, so a
    dependency a page dropped (a renamed function's slice, say) keeps its
    entry; comparing a file's recorded content must go through these keys.

    Args:
        manifest: The loaded manifest.

    Returns:
        Page dependencies, file-backed global inputs, import-time state files
        and memo source closures (paths or function slices).
    """
    entries: set[str] = set()
    for entry in manifest.get("pages", {}).values():
        entries.update(entry.get("deps", ()))
    entries.update(
        path for label, path in manifest.get("globals", {}).items() if label != "reflex"
    )
    entries.update(manifest.get("module_states", {}).get("files", ()))
    for memo in manifest.get("memo_files", {}).values():
        entries.update(memo.get("deps", ()))
    return entries


def manifest_dependency_files(manifest: dict[str, Any]) -> set[str]:
    """Every file the manifest records as a compile input.

    Args:
        manifest: The loaded manifest.

    Returns:
        The files of :func:`manifest_dependency_entries` plus the global
        inputs recorded as absent.
    """
    files = {
        page_cache.dep_file(dep)
        for dep in manifest_dependency_entries(manifest)
        if dep != page_cache.VOLATILE_DEP
    }
    files.update(manifest.get("globals_absent", ()))
    return files


def _manifest_text(manifest: dict[str, Any]) -> str:
    """Serialize the manifest, including the current import-name parse cache.

    Args:
        manifest: The manifest to serialize.

    Returns:
        The manifest JSON.
    """
    manifest["import_names"] = page_cache.export_import_names_cache()
    return json_dumps(manifest)


def _write(manifest: dict[str, Any]) -> None:
    """Persist the manifest.

    Args:
        manifest: The manifest to write.
    """
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_manifest_text(manifest), encoding="utf-8")


def write_manifest(
    compile_ctx: CompileContext,
    pages: Sequence[PageDefinition],
    install_imports: ParsedImportDict,
    root: Path | None = None,
    *,
    plugin_sources: dict[str, str] | None = None,
    contexts_snapshot: compiler_utils.ContextsSnapshot | None = None,
    registrations: dict[str, str] | None = None,
) -> None:
    """Persist a manifest of the just-completed full compile.

    Best-effort: any failure leaves no manifest (the next compile is full), it
    never breaks the build.

    Args:
        compile_ctx: The completed compile context (all pages compiled, the
            app root built).
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
        registrations: Each route's registration digest, taken before any page
            evaluated; computed now when absent.
    """
    try:
        state_index, _ = page_cache.state_dependency_index(root)
        hasher = page_cache.make_hasher()
        files: dict[str, page_cache.FileEntry] = {}
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
                state_slice=(
                    _state_slice(defined_states, *contexts_snapshot)
                    if defined_states and contexts_snapshot is not None
                    else None
                ),
                root=root,
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

        page_memo_keys = {
            tag for entry in pages_data.values() for tag in entry["memo_keys"]
        }
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
            # The states importing the app registers (see
            # ``_record_module_states``).
            "module_states": module_states,
            # The app root's inputs: the merged app wraps (by digest, in
            # insertion order) and the bundled libraries (see
            # ``_app_root_change``), plus the memo files only the root uses.
            "app_root": {
                "wraps": {
                    _wrap_key_str(key): _wrap_digest(component)
                    for key, component in compile_ctx.app_wrap_components.items()
                },
                "libraries": sorted(
                    RegistrationContext.ensure_context().bundled_libraries
                ),
                "memo_keys": sorted(
                    tag
                    for tag, _ in compile_ctx.auto_memo_components
                    if tag not in page_memo_keys
                ),
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
        # page by page (see ``_pages_mismatch``).
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


def _pages_mismatch(
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    registrations: dict[str, str],
) -> str | None:
    """Explain why the manifest's page set no longer matches, or None if it does.

    The page registry is an input of every page (a navigation built from the
    registered pages is common), so a page added, removed, reordered or
    registered differently (its title, say) is a change to every page.

    Args:
        pages: The current page definitions, in compile order.
        manifest: The loaded manifest.
        registrations: Each route's registration digest.

    Returns:
        A human-readable mismatch reason, or None when the pages match.
    """
    recorded = manifest["pages"]
    routes = [page.route for page in pages]
    if routes != list(recorded):
        changes = [
            f"{label} {format_path_list(items)}"
            for label, items in (
                ("added", set(routes) - set(recorded)),
                ("removed", set(recorded) - set(routes)),
            )
            if items
        ]
        if not changes:
            return "the page order changed"
        return f"the page set changed ({'; '.join(changes)})"
    for route in routes:
        if recorded[route]["registration"] != registrations[route]:
            return f"page {route!r} was registered differently"
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
) -> list[PageDefinition]:
    """Return the pages whose recorded dependencies changed.

    Globals and the page set are assumed already matched (see
    :func:`globals_mismatch` and :func:`_pages_mismatch`), so a page is a
    hit if every file in its recorded dependency set is unchanged. When the
    watcher reported the changed paths, a page depending on none of them
    skips the filesystem.

    Args:
        pages: The current page definitions.
        manifest: The loaded manifest.
        validator: The file validator bound to the manifest's file table.
        changed_hint: Resolved paths the watcher saw change, or None if unknown.

    Returns:
        The list of miss pages, in ``pages`` order.
    """
    manifest_pages = manifest["pages"]
    misses: list[PageDefinition] = []
    for page in pages:
        deps = manifest_pages[page.route]["deps"]
        if changed_hint is not None and changed_hint.isdisjoint(deps):
            continue
        if not validator.unchanged(deps):
            misses.append(page)
    return misses


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
    manifest: dict[str, Any], miss_ctx: CompileContext, miss_routes: set[str]
) -> str | None:
    """Find a re-evaluated page whose claims could shift other pages' names.

    Names in a family are handed out in evaluation order, so a re-evaluated
    page changing its claims in a family moves the names of later pages in
    that family. Pages that were not re-evaluated keep their recorded names,
    which is exact only when no family they use changed.

    Args:
        manifest: The loaded manifest.
        miss_ctx: The compile context of the re-evaluated pages.
        miss_routes: The re-evaluated routes.

    Returns:
        The first re-evaluated route that changed a shared family, or None.
    """
    shared = {
        family
        for route, entry in manifest["pages"].items()
        if route not in miss_routes
        for family in _claims_by_family(entry["dynamic_claims"])
    }
    for route in miss_routes:
        recorded = _claims_by_family(manifest["pages"][route]["dynamic_claims"])
        live = _claims_by_family(
            _dynamic_claims(miss_ctx.stateful_routes.get(route, ()))
        )
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


def _route_dropping_a_shared_state(
    manifest: dict[str, Any], miss_routes: Iterable[str]
) -> str | None:
    """Find a recompiled page whose recorded module state is gone.

    A page records the states its evaluation registered first. Another page
    using the same module state recorded none, so when the first page stops
    registering it, only a full compile keeps it. A local state belongs to
    its page alone.

    Args:
        manifest: The loaded manifest.
        miss_routes: The recompiled routes.

    Returns:
        The first such route, or None.
    """
    import reflex.istate.dynamic as istate_dynamic

    local_prefix = istate_dynamic.__name__.replace(".", "___") + "___"
    live = RegistrationContext.ensure_context().base_states
    for route in miss_routes:
        entry = manifest["pages"][route]
        if not entry["state_slice"]:
            continue
        for name in entry["state_slice"]["schema"]:
            if name not in live and not name.rpartition(".")[2].startswith(
                local_prefix
            ):
                return route
    return None


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

    Returns:
        The expanded miss list, in ``pages`` order.
    """
    if not miss_pages:
        return miss_pages
    miss_routes = {page.route for page in miss_pages}
    return [
        page
        for page in pages
        if page.route in miss_routes or manifest["pages"][page.route]["dynamic_claims"]
    ]


def _expand_miss_pages(
    miss_pages: list[PageDefinition],
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    stale_owner_routes: set[str],
) -> list[PageDefinition]:
    """Add the pages a rebuild of ``miss_pages`` must evaluate too.

    A route-owned memo entry whose dependency files changed needs its owner
    page re-evaluated: only that page's evaluation re-registers the memo
    definitions the rewrite compiles from.

    Args:
        miss_pages: The dependency-changed pages.
        pages: All current page definitions (in compile order).
        manifest: The loaded manifest.
        stale_owner_routes: Owners of route-owned memo records that changed.

    Returns:
        The expanded miss list, in ``pages`` order.
    """
    routes = {page.route for page in miss_pages} | stale_owner_routes
    miss_pages = [page for page in pages if page.route in routes]
    if _predict_dynamic_names:
        return miss_pages
    return _with_dynamic_state_pages(miss_pages, pages, manifest)


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
    """Resolve the mirrored output file path for a user memo's source module.

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


def _memo_file(tag: str) -> str:
    """The content-addressed file of an auto memo.

    Args:
        tag: The memo's export name, derived from its rendered body.

    Returns:
        The absolute output path string.
    """
    from reflex.compiler import utils as compiler_utils

    return compiler_utils.get_memo_component_path(tag)


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
    memo_uses: dict[tuple[str, str | None], Any],
    dirty_paths: set[str],
    changed_files: set[str],
) -> list[Any]:
    """Return the definitions of the memo files a rebuild writes.

    User memo output is grouped one file per source module, so a rewrite
    must carry every definition landing in that file: every user ``@rx.memo``
    whose output file is being rewritten because its recorded memo state
    changed (``dirty_paths``, see :func:`_dirty_memo_paths`), or whose module
    file (a recorded page dependency) changed, which the pre-evaluation state
    can't see for modules imported inside a page function. Auto memos are one
    file each, so the recompiled pages' uses are written as they are.

    Args:
        memo_uses: The auto memos the recompiled pages use.
        dirty_paths: Output paths whose stored memo state no longer matches.
        changed_files: The recorded dependency files whose content changed.

    Returns:
        The memo definitions to compile, user memos first (matching the full
        compile's emit order).
    """
    from reflex_base.components.memo import MEMOS

    user_memos = [
        memo
        for (_, source_module), memo in MEMOS.items()
        if _memo_output_path(source_module) in dirty_paths
        or _module_source_file(source_module) in changed_files
    ]
    return [*user_memos, *memo_uses.values()]


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
    path: str | Path, code: str, outputs: dict[Path, str] | None
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


def _app_root_change(
    manifest: dict[str, Any],
    pages: Sequence[PageDefinition],
    compiled_pages: dict[str, PageContext],
) -> str | None:
    """Explain how the recompiled pages changed the app root, or None.

    The app root is a function of the pages' merged app wraps (positioned by
    the first page requiring each, valued by the last, like the full
    compile's ``dict.update``). Rebuilding it from stored wraps would need
    every wrap component to survive a round trip through the manifest, so
    a changed root is left to a full compile instead; a page first gaining a
    provider is rare.

    Args:
        manifest: The loaded manifest.
        pages: All current page definitions (in compile order).
        compiled_pages: The recompiled pages' contexts, by route.

    Returns:
        A human-readable reason, or None when the root on disk still matches.
    """
    merged: dict[str, str] = {}
    providers: dict[str, str] = {}
    for page in pages:
        if (page_ctx := compiled_pages.get(page.route)) is not None:
            wraps = _record_app_wraps(page_ctx)
        else:
            wraps = manifest["pages"][page.route]["app_wraps"]
        for key, digest in wraps.items():
            merged[key] = digest
            providers[key] = page.route
    stored = manifest["app_root"]["wraps"]
    # Wraps of one priority nest in insertion order, so the order counts.
    if list(merged.items()) == list(stored.items()):
        return None
    for key in sorted(merged.keys() | stored.keys()):
        if merged.get(key) != stored.get(key):
            return f"page {providers.get(key)!r} changed the app wrap {key!r}"
    return "the app wraps changed their order"


def _new_bundled_libraries(manifest: dict[str, Any]) -> set[str]:
    """The libraries this compile bundled that the recorded app root lacks.

    The bundled-library file lists the registry of a full compile, which the
    recompiled pages' requests are only a part of; a library none of them
    needs can stay listed, a new one needs the file rewritten.

    Args:
        manifest: The loaded manifest.

    Returns:
        The libraries missing from the recorded registry.
    """
    live = RegistrationContext.ensure_context().bundled_libraries
    return set(live) - set(manifest["app_root"]["libraries"])


def _reconcile_memo_files(
    manifest: dict[str, Any],
    miss_routes: set[str],
    miss_memo_keys: dict[str, list[str]],
    emitted: Iterable[str],
) -> None:
    """Update the memo file manifest and drop the auto memo files no page uses.

    Args:
        manifest: The loaded manifest, with the hit pages' entries.
        miss_routes: The recompiled routes.
        miss_memo_keys: The memo keys of each recompiled route, now.
        emitted: The memo files this rebuild wrote.
    """
    from reflex.compiler import utils as compiler_utils

    used = set(manifest["app_root"]["memo_keys"])
    for route, entry in manifest["pages"].items():
        used.update(
            miss_memo_keys[route] if route in miss_routes else entry["memo_keys"]
        )
    dropped = {
        _memo_file(tag)
        for route in miss_routes
        for tag in manifest["pages"][route]["memo_keys"]
        if tag not in used
    }
    compiler_utils.reconcile_memo_manifest(emitted, dropped)


def _enable_radix_for_hit_pages(
    compiler_plugins: Sequence[Plugin], manifest: dict[str, Any], miss_routes: set[str]
) -> None:
    """Enable the implicit Radix Themes plugin when a reused page needs it.

    The implicit plugin enables itself while compiling a Radix component; a
    page reused from disk is not compiled, so without this the stylesheet,
    the theme and the package would drop out of a rebuild that re-evaluates
    no Radix page.

    Args:
        compiler_plugins: The resolved compiler plugins for this compile.
        manifest: The loaded manifest.
        miss_routes: The recompiled routes (compiled, so they enable it
            themselves).
    """
    from reflex_components_radix.plugin import RadixThemesPlugin

    for plugin in compiler_plugins:
        if (
            isinstance(plugin, RadixThemesPlugin)
            and not plugin.enabled
            and any(
                entry["radix"]
                for route, entry in manifest["pages"].items()
                if route not in miss_routes
            )
        ):
            plugin.enabled = True


def try_incremental_rebuild(
    app: App,
    *,
    compiler_plugins: Sequence[Plugin],
    prerender_routes: bool,
    root: Path | None = None,
    use_rich: bool = True,
    outputs: dict[Path, str] | None = None,
    registrations: dict[str, str] | None = None,
) -> bool | CompileContext:
    """Attempt a disk-cache-assisted partial rebuild; report whether it ran.

    Returns False (so the caller does a full compile) whenever anything is
    unsafe to reuse: no/old manifest, a changed global input, a changed page
    set or registration. When a miss page turns out to have altered the app
    root's inputs or its stateful flag, the miss pages are already evaluated
    and rendered. A page is never evaluated twice in one process (its locally
    defined states would register under collision-suffixed names the backend
    does not use), so the context holding those compiled pages is returned
    instead of False, for the full compile to adopt (see
    ``CompileContext.absorb``).

    User-memo output files are reconciled against the manifest's stored memo
    record (see :func:`_memo_state_entries`): files whose record differs are
    rewritten. Auto memos are content-addressed, one file each, so the
    recompiled pages write theirs without touching any other page's; files
    no page uses any more are dropped.

    The ``assets`` copy is excluded from dependency tracking and always re-run
    (cheap, idempotent). The contexts file is rewritten only when a stateful
    miss changed its state config, and then from this process's state tree
    plus the manifest's stored contributions of the stateful hit pages, so no
    unchanged page is ever re-evaluated.

    On success, reports (at info level) how many pages were recompiled vs reused
    and, while recompiling, shows a progress bar over the changed pages so a hot
    reload makes the incremental work visible. The refreshed manifest is the
    last output: with ``outputs`` it is staged after every other file, so a
    manifest on disk never vouches for files that were not written.

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
    if registrations is None:
        registrations = registration_digests(pages)
    validator = page_cache.FileValidator(manifest["files"])
    changed_hint = _with_hinted_slices(_changed_hint, manifest)

    if (reason := globals_mismatch(manifest, validator=validator, root=root)) or (
        reason := _pages_mismatch(pages, manifest, registrations)
    ):
        _log_fallback(reason)
        return False

    resolved_root = (root or Path.cwd()).resolve()
    # The states importing the app registered (no page has evaluated yet).
    page_states = _hit_page_states(manifest, set())
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
    miss_pages = partition_pages(pages, manifest, validator, changed_hint)
    # User memo files are decided salsa-style: derive the files the current
    # memo registry demands and rewrite the ones whose stored record differs.
    # This catches what changed-file diffing structurally cannot: a memo
    # module the previous compile never saw (its file is in no recorded
    # dependency set). Only import-owned memos are comparable here
    # (pre-evaluation); route-owned entries are handled by owner status: a
    # changed dependency pulls the owner page into the miss set, and its
    # re-evaluation feeds the post-evaluation comparison below.
    memo_hasher = page_cache.make_hasher()
    memo_files_table: dict[str, page_cache.FileEntry] = {}
    memo_state = _memo_state_entries(
        memo_hasher, memo_files_table, resolved_root, lambda owner: owner is None
    )
    stored_memo_files = manifest["memo_files"]
    dirty_memo_paths = _dirty_memo_paths(
        memo_state, stored_memo_files, validator, changed_hint
    )
    stale_owner_routes = {
        owner
        for entry in stored_memo_files.values()
        if (owner := entry["owner_route"]) is not None
        and owner in manifest["pages"]
        and _memo_deps_changed(entry["deps"], validator, changed_hint)
    }
    changed_files: set[str] = set()
    if miss_pages or dirty_memo_paths or stale_owner_routes:
        changed_files = _changed_dependency_files(manifest, validator, changed_hint)
        miss_pages = _expand_miss_pages(miss_pages, pages, manifest, stale_owner_routes)
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
    _enable_radix_for_hit_pages(compiler_plugins, manifest, miss_routes)

    from reflex.compiler import compiler

    if miss_pages or dirty_memo_paths:
        # Match the full compile's clean bundling/memo state before compiling.
        compiler._reset_compile_registries(compiler_plugins)

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
        _disown_hit_page_states(miss_ctx, manifest, miss_routes)
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                _fall_back_after_evaluation(f"page {page.route!r} produced no output")
                return False

    if (
        _predict_dynamic_names
        and miss_ctx is not None
        and (route := _shifting_dynamic_claims(manifest, miss_ctx, miss_routes))
    ):
        _fall_back_after_evaluation(
            f"page {route!r} changed dynamic state names other pages share"
        )
    if route := _route_dropping_a_shared_state(manifest, miss_routes):
        _fall_back_after_evaluation(
            f"page {route!r} no longer registers a state other pages may use"
        )
        return miss_ctx if miss_ctx is not None else False
    if miss_ctx is not None and (
        reason := _app_root_change(manifest, pages, miss_ctx.compiled_pages)
    ):
        _fall_back_after_evaluation(reason)
        return miss_ctx

    # Write changed pages + their memo files; reuse everything else on disk.
    install_imports = _deserialize_imports(manifest["all_imports"])
    eval_memo_state: dict[str, dict[str, Any]] = {}
    emitted_memo_files: list[str] = []
    miss_memo_keys: dict[str, list[str]] = {}
    if miss_ctx is not None or dirty_memo_paths:
        memo_uses: dict[tuple[str, str | None], Any] = {}
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
                memo_uses.update(page_ctx.memo_uses)
                miss_memo_keys[page.route] = _memo_keys(page_ctx)
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
        memo_files, memo_imports = compiler.compile_memo_components(
            _memo_defs_for_rewrite(memo_uses, dirty_memo_paths, changed_files)
        )
        for mpath, mcode in memo_files:
            _save_incremental_output(mpath, mcode, outputs)
            emitted_memo_files.append(mpath)
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
    if module_states_changed or (
        miss_ctx is not None
        and any(
            route in miss_ctx.stateful_routes or manifest["pages"][route]["is_stateful"]
            for route in miss_routes
        )
    ):
        contexts_snapshot = _contexts_snapshot(app)
        changed_route = (
            "the app's states"
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
            state_imports: ParsedImportDict = {}
            context_path, context_code = compiler.compile_contexts(
                app._state,
                theme,
                contexts_snapshot=merged_snapshot,
                component_imports=state_imports,
            )
            _save_incremental_output(context_path, context_code, outputs)
            install_imports = merge_imports(install_imports, state_imports)

    # The bundled-library file and the app root reference every bundled
    # library; a library first requested by this rebuild (a recompiled page,
    # a state default) needs both rewritten, which only a full compile does.
    if new_libraries := _new_bundled_libraries(manifest):
        _fall_back_after_evaluation(
            f"new bundled libraries: {format_path_list(new_libraries)}"
        )
        return miss_ctx if miss_ctx is not None else False

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

    # The route table the production static server reads.
    _save_incremental_output(
        constants.Dirs.ROUTES_MANIFEST, json.dumps(app._page_routes), outputs
    )
    _reconcile_memo_files(manifest, miss_routes, miss_memo_keys, emitted_memo_files)

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
        },
        **memo_state,
        **eval_memo_state,
    }

    # Refresh the manifest for the next process; it is the last output.
    if _update_manifest_for_misses(
        manifest,
        miss_ctx,
        miss_pages,
        install_imports,
        root,
        contexts_snapshot=contexts_snapshot,
        memo_state=final_memo_state,
        memo_file_entries=memo_files_table,
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
        validator=validator,
    ):
        _save_incremental_output(_manifest_path(), _manifest_text(manifest), outputs)

    app._cached_component_counts = manifest_component_counts(manifest)
    return True


def manifest_component_counts(manifest: dict[str, Any]) -> dict[str, int]:
    """Sum the component counts the manifest records per page.

    The compile telemetry of a process that reused every page from disk, or
    compiled in a child, has no evaluated pages to count.

    Args:
        manifest: The loaded manifest.

    Returns:
        The count of each component class across the pages.
    """
    counts: dict[str, int] = {}
    for entry in manifest["pages"].values():
        for name, count in entry.get("component_counts", {}).items():
            counts[name] = counts.get(name, 0) + count
    return counts


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
    registrations: dict[str, str],
    module_states: dict[str, list[str]],
    validator: page_cache.FileValidator | None = None,
) -> bool:
    """Update the manifest entries for the recompiled pages.

    Also refreshes the stat keys of files that were touched without changing
    (so they are not re-hashed on every later reload). The caller persists
    the manifest when something changed.

    Args:
        manifest: The loaded manifest (mutated).
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
        registrations: Each route's registration digest.
        module_states: The import-time states and their source files.
        validator: The validator used for this rebuild, for its refreshed
            entries.

    Returns:
        Whether the manifest changed and must be written.
    """
    dirty = validator is not None and _refresh_file_table(manifest, validator)
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
                state_slice=(
                    _state_slice(defined_states, *contexts_snapshot)
                    if defined_states and contexts_snapshot is not None
                    else None
                ),
                root=root,
            )
        dirty = True
    if manifest["module_states"] != module_states:
        manifest["module_states"] = module_states
        dirty = True
    # A memo-only rewrite can add packages with no page recompiled.
    if (imports := _serialize_imports(all_imports)) != manifest["all_imports"]:
        manifest["all_imports"] = imports
        dirty = True
    return dirty
