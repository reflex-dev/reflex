"""Disk-persisted incremental compile cache for ``REFLEX_COMPILE_CACHE``.

The manifest stores only bookkeeping: per-page dependency hashes, app-wrap keys,
statefulness, and app-wide frontend imports. Rendered files stay in ``.web``.
When global inputs and routes still match, unchanged pages are reused from disk
and only dependency-changed pages are recompiled.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base import constants
from reflex_base.plugins import CompileContext, CompilerHooks
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

#: Bump when the manifest layout changes (old manifests are then ignored).
_SCHEMA = 6
#: Manifest filename under the web directory.
_MANIFEST_FILE = "reflex_compile_cache.json"


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
    console.info(f"Compile cache: falling back to a full compile — {reason}")


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


def _wrap_key_strs(keys: Any) -> list[str]:
    """Render app-wrap ``(priority, name)`` keys as sorted stable strings.

    Args:
        keys: An iterable of ``(priority, name)`` app-wrap keys.

    Returns:
        A sorted list of ``"priority:name"`` strings.
    """
    return sorted(f"{p}:{n}" for p, n in keys)


def _manifest_page_entry(
    page_ctx: PageContext,
    component: Any,
    state_index: dict[str, Path],
    hasher: Callable[[str], str | None],
    *,
    is_stateful: bool,
    state_fingerprint: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Build the manifest entry for one compiled page.

    Args:
        page_ctx: The compiled page context.
        component: The page component/callable used for dependency discovery.
        state_index: The state-context identifier -> file index.
        hasher: A memoized path -> content-hash function.
        is_stateful: Whether the page registered state during compile.
        state_fingerprint: Fingerprint of the page's contexts contribution
            (see ``_contexts_fingerprint``), or None for stateless pages.
        root: Project root for dependency discovery. Defaults to cwd.

    Returns:
        The JSON-able manifest entry for the page.
    """
    return {
        "dep_hashes": page_cache.page_dependency_hashes(
            page_ctx, component, state_index, hasher, root
        ),
        "app_wrap_keys": _wrap_key_strs(page_ctx.app_wrap_components.keys()),
        "is_stateful": is_stateful,
        "state_fingerprint": state_fingerprint,
        # Whether the page contributed auto memos: pages sharing a source
        # module share one memo output file, so a memo-contributing hit page
        # must be recompiled alongside a same-module miss (see
        # ``_with_module_siblings``).
        "has_memos": bool(page_ctx.memo_contributions),
    }


def _contexts_fingerprint(
    state_names: Sequence[str],
    initial_state: dict[str, Any],
    client_storage: dict[str, dict[str, Any]],
) -> str:
    """Fingerprint some states' contribution to the compiled contexts file.

    A state's contribution is exactly its initial-state slice plus its
    client-storage entries (see ``templates.context_template``), so equal
    fingerprints mean re-emitting the contexts file would leave these states'
    entries unchanged.

    Args:
        state_names: Full names of the states to fingerprint.
        initial_state: The complete initial-state mapping (full name -> vars).
        client_storage: The compiled client-storage mapping per storage kind.

    Returns:
        A stable hash of the states' contexts contribution.
    """
    payload = []
    for name in sorted(state_names):
        prefix = f"{name}."
        payload.append((
            name,
            initial_state.get(name),
            {
                kind: {k: v for k, v in entries.items() if k.startswith(prefix)}
                for kind, entries in client_storage.items()
            },
        ))
    return hashlib.sha256(json_dumps(payload).encode()).hexdigest()


def _contexts_snapshot(
    app: App | None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Capture the state-tree inputs of the contexts file.

    Args:
        app: The app being compiled (absent in bare compile contexts).

    Returns:
        The (initial state, client storage) mappings keyed by state full name,
        or None when there is no state tree.
    """
    if app is None or app._state is None:
        return None
    from reflex.compiler import utils as compiler_utils

    return (
        compiler_utils.compile_state(app._state),
        compiler_utils.compile_client_storage(app._state),
    )


def _changed_state_config_route(
    manifest: dict[str, Any],
    miss_ctx: CompileContext,
    snapshot: tuple[dict[str, Any], dict[str, Any]] | None,
) -> str | None:
    """Find the first recompiled stateful route whose state config changed.

    Compares each stateful miss page's just-evaluated states against the
    fingerprint recorded in the manifest. Only these pages' states can differ
    from the on-disk contexts file: hit pages' definitions are unchanged by
    construction (all their dependency files still match).

    Args:
        manifest: The loaded compile manifest.
        miss_ctx: The compile context of the recompiled pages.
        snapshot: The ``_contexts_snapshot`` of the app, or None when there is
            no state tree to fingerprint against.

    Returns:
        The first route requiring a contexts rebuild, or None if none do.
    """
    if snapshot is None:
        return next(iter(miss_ctx.stateful_routes))
    for route, defined_states in miss_ctx.stateful_routes.items():
        stored = manifest["pages"].get(route, {}).get("state_fingerprint")
        if stored != _contexts_fingerprint(defined_states, *snapshot):
            return route
    return None


def load_manifest() -> dict[str, Any] | None:
    """Load the persisted compile manifest, or None if absent/unusable.

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
    return data


def write_manifest(
    compile_ctx: CompileContext,
    pages: Sequence[PageDefinition],
    install_imports: ParsedImportDict,
    root: Path | None = None,
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
    """
    try:
        state_index, _ = page_cache.state_dependency_index(root)
        hasher = page_cache.make_hasher()
        epoch_inputs = page_cache.global_epoch_inputs(root, pages=pages)
        contexts_snapshot = (
            _contexts_snapshot(compile_ctx.app) if compile_ctx.stateful_routes else None
        )

        pages_data: dict[str, Any] = {}
        for page in pages:
            page_ctx = compile_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                return  # incomplete compile -> do not write a partial manifest
            defined_states = compile_ctx.stateful_routes.get(page.route)
            pages_data[page.route] = _manifest_page_entry(
                page_ctx,
                page.component,
                state_index,
                hasher,
                is_stateful=defined_states is not None,
                state_fingerprint=(
                    _contexts_fingerprint(defined_states, *contexts_snapshot)
                    if defined_states and contexts_snapshot is not None
                    else None
                ),
                root=root,
            )

        manifest = {
            "schema": _SCHEMA,
            "reflex_version": page_cache._reflex_version(),
            # Per-input digests (not one combined sha) so a later mismatch can
            # name the exact global input that changed.
            "epoch_inputs": epoch_inputs,
            "all_imports": _serialize_imports(install_imports),
            "pages": pages_data,
        }
        path = _manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    except Exception as exc:  # best-effort: never break the build
        console.debug(f"disk compile cache: manifest write skipped ({exc!r})")


def globals_mismatch(
    manifest: dict[str, Any],
    *,
    routes: set[str],
    root: Path | None = None,
) -> str | None:
    """Explain why the manifest's global inputs don't match, or None if they do.

    The fast rebuild needs the route set unchanged (adding/removing a route
    changes the shared nav on every page) and the global inputs unchanged (Reflex
    version + config/lockfiles + the app-level config files: the entrypoint and
    the theme/app-wrap/stylesheet modules it imports, which configure the app-wide
    files reused on disk). Everything else is decided per page via its dependency
    set, so a shared-component or markdown edit no longer blocks the fast path.
    Only the pages that depend on the changed file miss.

    Global inputs are validated by re-hashing the manifest's *stored* input set
    (see :func:`page_cache.changed_epoch_inputs`), never by recomputing the set
    in this process — set membership is only decided when a full compile writes
    the manifest.

    Args:
        manifest: The loaded manifest.
        routes: The current set of page routes.
        root: Project root the stored inputs resolve against (also used to
            shorten paths in the reason). Defaults to cwd.

    Returns:
        A human-readable mismatch reason, or None when the global inputs match.
    """
    old_version = manifest.get("reflex_version")
    if old_version != page_cache._reflex_version():
        return (
            f"reflex version changed ({old_version} -> {page_cache._reflex_version()})"
        )
    old_routes = set(manifest.get("pages", {}))
    if old_routes != routes:
        parts = []
        if added := routes - old_routes:
            parts.append(f"added {format_path_list(added)}")
        if removed := old_routes - routes:
            parts.append(f"removed {format_path_list(removed)}")
        return f"route set changed ({'; '.join(parts)})"
    root = (root or Path.cwd()).resolve()
    if stale := page_cache.changed_epoch_inputs(manifest.get("epoch_inputs", {}), root):
        labels = {label.removeprefix("app:") for label in stale}
        return f"global input(s) changed: {format_path_list(labels, root)}"
    return None


def partition_pages(
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
    hasher: Callable[[str], str | None],
) -> list[PageDefinition]:
    """Return the pages whose dependency set changed since the manifest.

    Globals are assumed already matched (see :func:`globals_match`), so a page is
    a hit if every file in its recorded dependency set is byte-unchanged.

    Args:
        pages: The current page definitions.
        manifest: The loaded manifest.
        hasher: A memoized path -> content-hash function.

    Returns:
        The list of miss pages (a dependency changed) to recompile.
    """
    manifest_pages = manifest["pages"]
    return [
        page
        for page in pages
        if not page_cache.deps_unchanged(
            manifest_pages[page.route]["dep_hashes"], hasher
        )
    ]


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


def _changed_dependency_files(
    manifest: dict[str, Any], hasher: Callable[[str], str | None]
) -> set[str]:
    """Return every recorded dependency file whose content changed.

    Args:
        manifest: The loaded manifest.
        hasher: A memoized path -> content-hash function.

    Returns:
        The set of changed dependency file paths.
    """
    return {
        path
        for entry in manifest["pages"].values()
        for path, digest in entry["dep_hashes"].items()
        if hasher(path) != digest
    }


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


def _complete_memo_defs(
    contributions: dict[tuple[str, str | None], Any],
    changed_files: set[str],
) -> list[Any]:
    """Return the full definition set for the memo files being rewritten.

    Memo output is grouped one file per source module, so a rewrite must carry
    every definition landing in that file: user ``@rx.memo`` definitions from
    the global registry that share a module with a recompiled contribution,
    plus user memos whose own module file changed (an edited memo body must be
    re-emitted even though only its importer pages missed).

    Args:
        contributions: The recompiled pages' auto-memo contributions.
        changed_files: The dependency files whose content changed.

    Returns:
        The memo definitions to compile, user memos first (matching the full
        compile's emit order).
    """
    from reflex_base.components.memo import MEMOS
    from reflex_base.utils import memo_paths

    dirty_segments = {
        segments
        for definition in contributions.values()
        if (
            segments := memo_paths.module_to_mirrored_segments(definition.source_module)
        )
        is not None
    }
    user_memos = [
        memo
        for memo in MEMOS.values()
        if memo_paths.module_to_mirrored_segments(memo.source_module) in dirty_segments
        or _module_source_file(memo.source_module) in changed_files
    ]
    return [*user_memos, *contributions.values()]


def try_incremental_rebuild(
    app: App,
    *,
    compiler_plugins: Any,
    prerender_routes: bool,
    root: Path | None = None,
    use_rich: bool = True,
) -> bool:
    """Attempt a disk-cache-assisted partial rebuild; report whether it ran.

    Returns False (so the caller does a full compile) whenever anything is
    unsafe to reuse: no/old manifest, a changed global input, a route change, or
    a miss page that altered its app-wrap set or stateful flag.

    The ``assets`` copy is excluded from dependency tracking and always re-run
    (cheap, idempotent). The contexts file is rewritten only when a stateful
    page missed — and then only after evaluating the stateful hit pages, so the
    state registry it is compiled from is complete (it must keep the states
    that only a page's evaluation registers, e.g. exec'd docs demos).

    On success, reports (at info level) how many pages were recompiled vs reused
    and, while recompiling, shows a progress bar over the changed pages so a hot
    reload makes the incremental work visible.

    Args:
        app: The app being compiled.
        compiler_plugins: The resolved compiler plugins for this compile.
        prerender_routes: Whether to prerender routes.
        root: Project root for fingerprinting. Defaults to cwd.
        use_rich: Whether to use a rich progress bar (else a plain fallback).

    Returns:
        True if the partial rebuild completed (the caller should return), else
        False (the caller should run a full compile).
    """
    manifest = load_manifest()
    if manifest is None:
        _log_fallback(
            "no reusable manifest (first compile, unreadable, or schema changed)"
        )
        return False

    pages = list(app._unevaluated_pages.values())
    routes = {p.route for p in pages}
    hasher = page_cache.make_hasher()

    if (reason := globals_mismatch(manifest, routes=routes, root=root)) is not None:
        _log_fallback(reason)
        return False

    resolved_root = (root or Path.cwd()).resolve()
    miss_pages = partition_pages(pages, manifest, hasher)
    changed_files: set[str] = set()
    if miss_pages:
        # Nearly free: partition_pages already hashed every dependency file
        # into the memoized hasher.
        changed_files = _changed_dependency_files(manifest, hasher)
        miss_pages = _with_module_siblings(miss_pages, pages, manifest)
        console.info(
            f"Compile cache: recompiling {len(miss_pages)}/{len(pages)} pages; "
            f"changed file(s): {format_path_list(changed_files, resolved_root)}"
        )
    else:
        console.info(f"Compile cache: reusing all {len(pages)} pages from disk")
    miss_routes = {p.route for p in miss_pages}

    # Recompile only the source-changed pages.
    miss_ctx = None
    if miss_pages:
        from reflex_base.components.dynamic import (
            bundle_library,
            reset_bundled_libraries,
        )
        from reflex_base.components.memo import reset_memo_component_classes

        from reflex.compiler.compiler import make_compile_progress

        # Match the full compile's clean bundling/memo state before compiling.
        reset_bundled_libraries()
        reset_memo_component_classes()
        for plugin in compiler_plugins:
            for dependency in plugin.get_frontend_dependencies():
                bundle_library(dependency)
        miss_ctx = CompileContext(
            app=app,
            pages=miss_pages,
            hooks=CompilerHooks(
                plugins=default_page_plugins(style=app.style, plugins=compiler_plugins)
            ),
        )
        # Progress over the changed pages (evaluate + render each), so a hot
        # reload shows how much is being recompiled.
        progress = make_compile_progress(use_rich)
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
        # Guard: a miss must not change the app-wrap set or its stateful flag, or
        # the reused on-disk app root / state marker would be wrong.
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                _log_fallback(f"page {page.route!r} produced no output")
                return False
            entry = manifest["pages"][page.route]
            if (
                _wrap_key_strs(page_ctx.app_wrap_components.keys())
                != entry["app_wrap_keys"]
            ):
                _log_fallback(f"page {page.route!r} changed its app-wrap set")
                return False
            if (page.route in miss_ctx.stateful_routes) != entry["is_stateful"]:
                _log_fallback(f"page {page.route!r} changed statefulness")
                return False

    from reflex.compiler import compiler

    # Write changed pages + their memo files; reuse everything else on disk.
    install_imports = _deserialize_imports(manifest["all_imports"])
    if miss_ctx is not None:
        memo_contributions: dict[tuple[str, str | None], Any] = {}
        miss_imports = []
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages[page.route]
            # Both are guaranteed non-None by the guard loop above.
            output_path = page_ctx.output_path
            output_code = page_ctx.output_code
            if output_path is None or output_code is None:
                _log_fallback(f"page {page.route!r} lost its output before write")
                return False
            compiler.utils.write_file(
                compiler.utils.resolve_path_of_web_dir(output_path),
                output_code,
            )
            memo_contributions.update(page_ctx.memo_contributions)
            miss_imports.append(page_ctx.frontend_imports)
        # Memo output files are grouped per source module, so compile them once
        # with the complete definition set (all recompiled pages' contributions
        # plus the user memos sharing those files or whose module changed).
        memo_files, memo_imports = compiler.compile_memo_components(
            _complete_memo_defs(memo_contributions, changed_files)
        )
        for mpath, mcode in memo_files:
            compiler.utils.write_file(
                compiler.utils.resolve_path_of_web_dir(mpath), mcode
            )
        # Merge once: re-merging the app-wide set per page re-walks its ~100k
        # entries each time.
        install_imports = merge_imports(install_imports, *miss_imports, memo_imports)

    # Record which routes are stateful: miss pages from this compile, hit pages
    # from the manifest, so the stateful-pages marker is complete. We do NOT
    # re-evaluate hit pages to register their state in this process: it only
    # produces .web and exits (the daemon, the initial compile, and CLI compiles
    # never serve), and the serving backend re-evaluates the marked stateful
    # pages itself. Re-evaluating them here re-ran the full render pipeline for
    # every unchanged stateful page on every edit, for nothing.
    stateful_routes: dict[str, None] = {}
    for page in pages:
        if page.route in miss_routes:
            if miss_ctx is not None and page.route in miss_ctx.stateful_routes:
                stateful_routes[page.route] = None
        elif manifest["pages"][page.route]["is_stateful"]:
            stateful_routes[page.route] = None

    app._stateful_pages.update(stateful_routes)
    app._write_stateful_pages_marker()
    app._add_optional_endpoints()
    app._validate_var_dependencies()

    # The contexts file holds EVERY state's defaults/dispatchers, including
    # states only registered while their page evaluates (exec'd docs demos,
    # dynamically imported modules). This process evaluated just the miss
    # pages, so its registry is incomplete; rewriting contexts from it would
    # drop the hit pages' states and break the frontend's dispatch map. Only a
    # stateful miss can change state config — and only its OWN states can
    # differ from the on-disk contexts file, so first fingerprint those
    # against the manifest: a content-only edit leaves them identical and the
    # contexts file is reused untouched. Otherwise evaluate the stateful hit
    # pages (so the registry is complete) and rewrite contexts.
    contexts_snapshot: tuple[dict[str, Any], dict[str, Any]] | None = None
    if miss_ctx is not None and miss_ctx.stateful_routes:
        contexts_snapshot = _contexts_snapshot(app)
        changed_route = _changed_state_config_route(
            manifest, miss_ctx, contexts_snapshot
        )
        if changed_route is None:
            console.info(
                "Compile cache: recompiled pages define unchanged states; "
                "reusing contexts file"
            )
        else:
            console.info(
                f"Compile cache: page {changed_route!r} changed its state "
                "config; rebuilding contexts"
            )
            stateful_hits = [
                route
                for route, entry in manifest["pages"].items()
                if entry["is_stateful"] and route not in miss_routes
            ]
            with console.timing("Evaluate stateful hit pages (contexts)"):
                for route in stateful_hits:
                    app._compile_page(route, save_page=False)

            from reflex_components_radix.plugin import RadixThemesPlugin

            theme = next(
                (
                    plugin.get_theme()
                    for plugin in compiler_plugins
                    if isinstance(plugin, RadixThemesPlugin)
                ),
                None,
            )
            context_path, context_code = compiler.compile_contexts(app._state, theme)
            compiler.utils.write_file(
                compiler.utils.resolve_path_of_web_dir(context_path), context_code
            )

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

    with console.timing("Install Frontend Packages"):
        app._get_frontend_packages(install_imports)
    frontend_skeleton.update_react_router_config(prerender_routes=prerender_routes)
    frontend_skeleton.update_entry_client()
    frontend_skeleton.initialize_vite_config()

    # Refresh the manifest for the next process.
    _update_manifest_for_misses(
        manifest,
        miss_ctx,
        miss_pages,
        install_imports,
        root,
        contexts_snapshot=contexts_snapshot,
    )

    return True


def _update_manifest_for_misses(
    manifest: dict[str, Any],
    miss_ctx: CompileContext | None,
    miss_pages: Sequence[PageDefinition],
    all_imports: ParsedImportDict,
    root: Path | None = None,
    *,
    contexts_snapshot: tuple[dict[str, Any], dict[str, Any]] | None = None,
) -> None:
    """Update the on-disk manifest entries for the recompiled pages.

    Args:
        manifest: The loaded manifest (mutated and rewritten).
        miss_ctx: The compile context of the recompiled pages, if any.
        miss_pages: The recompiled page definitions.
        all_imports: The complete frontend import set after recompiling misses.
        root: Project root for dependency discovery. Defaults to cwd.
        contexts_snapshot: The app's ``_contexts_snapshot`` for fingerprinting
            stateful pages, or None when no miss page was stateful.
    """
    if miss_ctx is None or not miss_pages:
        return
    try:
        state_index, _ = page_cache.state_dependency_index(root)
        hasher = page_cache.make_hasher()
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages[page.route]
            defined_states = miss_ctx.stateful_routes.get(page.route)
            manifest["pages"][page.route] = _manifest_page_entry(
                page_ctx,
                page.component,
                state_index,
                hasher,
                is_stateful=defined_states is not None,
                state_fingerprint=(
                    _contexts_fingerprint(defined_states, *contexts_snapshot)
                    if defined_states and contexts_snapshot is not None
                    else None
                ),
                root=root,
            )
        manifest["all_imports"] = _serialize_imports(all_imports)
        _manifest_path().write_text(json.dumps(manifest), encoding="utf-8")
    except Exception as exc:  # best-effort
        console.debug(f"disk compile cache: manifest refresh skipped ({exc!r})")
