"""Disk-persisted incremental compile cache for ``REFLEX_COMPILE_CACHE``.

The manifest stores only bookkeeping: per-page dependency hashes, app-wrap keys,
statefulness, and app-wide frontend imports. Rendered files stay in ``.web``.
When global inputs and routes still match, unchanged pages are reused from disk
and only dependency-changed pages are recompiled.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any

from reflex_base.plugins import CompileContext, CompilerHooks
from reflex_base.utils.imports import ImportVar, merge_imports

from reflex.compiler import page_cache
from reflex.compiler.plugins import default_page_plugins
from reflex.utils import console, prerequisites

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from reflex_base.plugins import PageContext, PageDefinition
    from reflex_base.utils.imports import ParsedImportDict

    from reflex.app import App

#: Bump when the manifest layout changes (old manifests are then ignored).
_SCHEMA = 3
#: Manifest filename under the web directory.
_MANIFEST_FILE = "reflex_compile_cache.json"


def _manifest_path() -> Path:
    return prerequisites.get_web_dir() / _MANIFEST_FILE


def _serialize_imports(imports: ParsedImportDict) -> dict[str, list[dict[str, Any]]]:
    """Serialize a parsed import dict to JSON-able primitives.

    Args:
        imports: The parsed import dict to serialize.

    Returns:
        A JSON-serializable representation.
    """
    return {lib: [dataclasses.asdict(iv) for iv in ivs] for lib, ivs in imports.items()}


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
    root: Path | None = None,
) -> dict[str, Any]:
    """Build the manifest entry for one compiled page.

    Args:
        page_ctx: The compiled page context.
        component: The page component/callable used for dependency discovery.
        state_index: The state-context identifier -> file index.
        hasher: A memoized path -> content-hash function.
        is_stateful: Whether the page registered state during compile.
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
    }


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
        epoch = page_cache.global_epoch(root, pages=pages)

        pages_data: dict[str, Any] = {}
        for page in pages:
            page_ctx = compile_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                return  # incomplete compile -> do not write a partial manifest
            pages_data[page.route] = _manifest_page_entry(
                page_ctx,
                page.component,
                state_index,
                hasher,
                is_stateful=page.route in compile_ctx.stateful_routes,
                root=root,
            )

        manifest = {
            "schema": _SCHEMA,
            "reflex_version": page_cache._reflex_version(),
            "epoch": epoch,
            "all_imports": _serialize_imports(install_imports),
            "pages": pages_data,
        }
        path = _manifest_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
    except Exception as exc:  # best-effort: never break the build
        console.debug(f"disk compile cache: manifest write skipped ({exc!r})")


def globals_match(
    manifest: dict[str, Any],
    *,
    routes: set[str],
    epoch: str,
) -> bool:
    """Whether the manifest's genuinely-global inputs match the current compile.

    The fast rebuild needs the route set unchanged (adding/removing a route
    changes the shared nav on every page) and the global epoch unchanged (Reflex
    version + config/lockfiles + the app-level config files: the entrypoint and
    the theme/app-wrap/stylesheet modules it imports, which configure the app-wide
    files reused on disk). Everything else is decided per page via its dependency
    set, so a shared-component or markdown edit no longer blocks the fast path.
    Only the pages that depend on the changed file miss.

    Args:
        manifest: The loaded manifest.
        routes: The current set of page routes.
        epoch: The current global epoch (see :func:`page_cache.global_epoch`).

    Returns:
        True if the global inputs match.
    """
    return (
        manifest.get("reflex_version") == page_cache._reflex_version()
        and set(manifest.get("pages", {})) == routes
        and manifest.get("epoch") == epoch
    )


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
        return False

    pages = list(app._unevaluated_pages.values())
    routes = {p.route for p in pages}
    hasher = page_cache.make_hasher()
    epoch = page_cache.global_epoch(root, pages=pages)

    if not globals_match(manifest, routes=routes, epoch=epoch):
        return False

    miss_pages = partition_pages(pages, manifest, hasher)
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
                return False
            entry = manifest["pages"][page.route]
            if (
                _wrap_key_strs(page_ctx.app_wrap_components.keys())
                != entry["app_wrap_keys"]
            ):
                return False
            if (page.route in miss_ctx.stateful_routes) != entry["is_stateful"]:
                return False

    from reflex.compiler import compiler

    # Write changed pages + their memo files; reuse everything else on disk.
    install_imports = _deserialize_imports(manifest["all_imports"])
    if miss_ctx is not None:
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages[page.route]
            # Both are guaranteed non-None by the guard loop above.
            output_path = page_ctx.output_path
            output_code = page_ctx.output_code
            if output_path is None or output_code is None:
                return False
            compiler.utils.write_file(
                compiler.utils.resolve_path_of_web_dir(output_path),
                output_code,
            )
            memo_defs = list(page_ctx.memo_contributions.values())
            memo_files, memo_imports = compiler.compile_memo_components(memo_defs)
            for mpath, mcode in memo_files:
                compiler.utils.write_file(
                    compiler.utils.resolve_path_of_web_dir(mpath), mcode
                )
            install_imports = merge_imports(
                install_imports, page_ctx.frontend_imports, memo_imports
            )

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

    # Frontend packages + routing scaffolding (cheap, idempotent).
    from reflex.utils import frontend_skeleton

    with console.timing("Install Frontend Packages"):
        app._get_frontend_packages(install_imports)
    frontend_skeleton.update_react_router_config(prerender_routes=prerender_routes)
    frontend_skeleton.update_entry_client()

    # Refresh the manifest for the next process.
    _update_manifest_for_misses(manifest, miss_ctx, miss_pages, install_imports, root)

    return True


def _update_manifest_for_misses(
    manifest: dict[str, Any],
    miss_ctx: CompileContext | None,
    miss_pages: Sequence[PageDefinition],
    all_imports: ParsedImportDict,
    root: Path | None = None,
) -> None:
    """Update the on-disk manifest entries for the recompiled pages.

    Args:
        manifest: The loaded manifest (mutated and rewritten).
        miss_ctx: The compile context of the recompiled pages, if any.
        miss_pages: The recompiled page definitions.
        all_imports: The complete frontend import set after recompiling misses.
        root: Project root for dependency discovery. Defaults to cwd.
    """
    if miss_ctx is None or not miss_pages:
        return
    try:
        state_index, _ = page_cache.state_dependency_index(root)
        hasher = page_cache.make_hasher()
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages[page.route]
            manifest["pages"][page.route] = _manifest_page_entry(
                page_ctx,
                page.component,
                state_index,
                hasher,
                is_stateful=page.route in miss_ctx.stateful_routes,
                root=root,
            )
        manifest["all_imports"] = _serialize_imports(all_imports)
        _manifest_path().write_text(json.dumps(manifest), encoding="utf-8")
    except Exception as exc:  # best-effort
        console.debug(f"disk compile cache: manifest refresh skipped ({exc!r})")
