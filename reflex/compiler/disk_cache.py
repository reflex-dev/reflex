"""Experimental disk-persisted incremental compile cache (Tier 3, flag-gated).

Enabled by ``REFLEX_DISK_COMPILE_CACHE``. When off (default), nothing changes.

Tier 2 (``page_cache._PAGE_STORE``) reuses compiled pages within one process, so
it never fires in the ``reflex run`` edit loop — the reloader respawns a fresh
worker subprocess on every ``.py`` change, starting with an empty in-memory
store. This tier persists each page's *serializable* contribution to disk so the
fresh worker can reuse it.

**What is persisted** (``.web/reflex_compile_cache.json``): per page, its source
fingerprint, its rendered ``output_code`` and path, its ``frontend_imports``
(``ImportVar`` is a frozen dataclass of primitives), its app-wrap key-set, and
whether evaluating it registered new state. App-wide: the shared fingerprint, the
fine-grained state hashes, the reflex version, and the merged imports. The
manifest deliberately stores **no rendered memo files**: a hit page's memo files
are already on disk from the prior compile, and a miss page re-renders its own on
recompile — so writing the manifest is just string/key serialization, never a
second memo render.

**The fast path** (``try_incremental_rebuild``). On a fresh compile it reuses the
manifest only when the global inputs match (reflex version, route set, shared
fingerprint, *and* every state hash). That restricts a fast rebuild to **pure
page-body edits** — so the on-disk app-wide files (app root, contexts, theme,
stylesheet, …) are all still valid and only changed pages need work. Then:

- A *stateless* hit page is skipped entirely (its frontend file is reused and
  evaluating it would register nothing).
- A *stateful* hit page is re-evaluated for the backend only (to re-register its
  state classes), reusing its frontend file. ``is_stateful`` is true exactly
  when the page's first eval grew the state registry, so this is precisely the
  set whose state would otherwise go missing.
- A *miss* page (source changed) is fully recompiled and its files rewritten.

After recompiling misses, two guards must hold or the whole thing falls back to a
full compile (return False): each miss page's app-wrap key-set and stateful flag
must be unchanged (otherwise the reused on-disk app root would be wrong). Any
state edit, shared-file edit, route add/remove, or version change also falls back
to a full compile. ``REFLEX_COMPILE_CACHE_VERIFY`` is the backstop for an app.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
from typing import TYPE_CHECKING, Any

from reflex_base.plugins import CompileContext, CompilerHooks
from reflex_base.utils.imports import ImportVar, merge_imports

from reflex.compiler import page_cache
from reflex.compiler.plugins import default_page_plugins
from reflex.utils import console, prerequisites

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from reflex_base.plugins import PageDefinition
    from reflex_base.utils.imports import ParsedImportDict

    from reflex.app import App

#: Bump when the manifest layout changes (old manifests are then ignored).
_SCHEMA = 1
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
    root: Path | None = None,
) -> None:
    """Persist a manifest of the just-completed full compile.

    Best-effort: any failure leaves no manifest (the next compile is full), it
    never breaks the build.

    Args:
        compile_ctx: The completed compile context (all pages compiled).
        pages: The full list of page definitions that were compiled.
        root: Project root for fingerprinting. Defaults to cwd.
    """
    try:
        page_files = page_cache.page_module_files(p.component for p in pages)
        _, fine_state_files = page_cache.state_dependency_index(root)
        shared_fp = page_cache.shared_fingerprint(page_files | fine_state_files, root)
        state_hashes = page_cache.file_hashes(fine_state_files)

        pages_data: dict[str, Any] = {}
        for page in pages:
            page_ctx = compile_ctx.compiled_pages.get(page.route)
            if (
                page_ctx is None
                or page_ctx.output_code is None
                or page_ctx.output_path is None
            ):
                return  # incomplete compile -> do not write a partial manifest
            pages_data[page.route] = {
                "page_source_fp": page_cache.page_source_fingerprint(page.component),
                "output_path": page_ctx.output_path,
                "output_code": page_ctx.output_code,
                "frontend_imports": _serialize_imports(page_ctx.frontend_imports),
                "app_wrap_keys": _wrap_key_strs(page_ctx.app_wrap_components.keys()),
                "is_stateful": page.route in compile_ctx.stateful_routes,
            }

        manifest = {
            "schema": _SCHEMA,
            "reflex_version": page_cache._reflex_version(),
            "shared_fp": shared_fp,
            "state_hashes": state_hashes,
            "all_imports": _serialize_imports(compile_ctx.all_imports),
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
    shared_fp: str,
    state_hashes: dict[str, str],
) -> bool:
    """Whether the manifest's global inputs match the current compile.

    A fast rebuild is only attempted when the reflex version, route set, shared
    fingerprint, and every fine-grained state hash are unchanged — restricting it
    to pure page-body edits, so all on-disk app-wide files remain valid.

    Args:
        manifest: The loaded manifest.
        routes: The current set of page routes.
        shared_fp: The current coarse shared fingerprint.
        state_hashes: The current fine-grained state file hashes.

    Returns:
        True iff every global input matches.
    """
    return (
        manifest.get("reflex_version") == page_cache._reflex_version()
        and set(manifest.get("pages", {})) == routes
        and manifest.get("shared_fp") == shared_fp
        and manifest.get("state_hashes", {}) == state_hashes
    )


def partition_pages(
    pages: Sequence[PageDefinition],
    manifest: dict[str, Any],
) -> list[PageDefinition]:
    """Return the pages whose own source changed since the manifest.

    Globals are assumed already matched (see :func:`globals_match`), so a page is
    a hit unless its source fingerprint differs.

    Args:
        pages: The current page definitions.
        manifest: The loaded manifest.

    Returns:
        The list of miss pages (source changed) to recompile.
    """
    manifest_pages = manifest["pages"]
    return [
        page
        for page in pages
        if page_cache.page_source_fingerprint(page.component)
        != manifest_pages[page.route]["page_source_fp"]
    ]


def try_incremental_rebuild(
    app: App,
    *,
    compiler_plugins: Any,
    prerender_routes: bool,
    root: Path | None = None,
) -> bool:
    """Attempt a disk-cache-assisted partial rebuild; report whether it ran.

    Returns False (so the caller does a full compile) whenever anything is
    unsafe to reuse: no/old manifest, a changed global input, a route change, or
    a miss page that altered its app-wrap set or stateful flag.

    Args:
        app: The app being compiled.
        compiler_plugins: The resolved compiler plugins for this compile.
        prerender_routes: Whether to prerender routes.
        root: Project root for fingerprinting. Defaults to cwd.

    Returns:
        True if the partial rebuild completed (the caller should return), else
        False (the caller should run a full compile).
    """
    manifest = load_manifest()
    if manifest is None:
        return False

    pages = list(app._unevaluated_pages.values())
    routes = {p.route for p in pages}
    page_files = page_cache.page_module_files(p.component for p in pages)
    _, fine_state_files = page_cache.state_dependency_index(root)
    shared_fp = page_cache.shared_fingerprint(page_files | fine_state_files, root)
    state_hashes = page_cache.file_hashes(fine_state_files)

    if not globals_match(
        manifest, routes=routes, shared_fp=shared_fp, state_hashes=state_hashes
    ):
        return False

    miss_pages = partition_pages(pages, manifest)
    miss_routes = {p.route for p in miss_pages}

    # Recompile only the source-changed pages.
    miss_ctx = None
    if miss_pages:
        from reflex_base.components.dynamic import (
            bundle_library,
            reset_bundled_libraries,
        )
        from reflex_base.components.memo import reset_memo_component_classes

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
        with miss_ctx:
            miss_ctx.compile()
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

    # Re-register state for stateful hit pages (skipping eval would drop their
    # state classes); stateless hits need nothing.
    stateful_routes: dict[str, None] = {}
    with console.timing("Evaluate Pages (Backend)"):
        for page in pages:
            if page.route in miss_routes:
                if miss_ctx is not None and page.route in miss_ctx.stateful_routes:
                    stateful_routes[page.route] = None
                continue
            if manifest["pages"][page.route]["is_stateful"]:
                app._compile_page(page.route, save_page=False)
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
    _update_manifest_for_misses(manifest, miss_ctx, miss_pages)

    with contextlib.suppress(Exception):
        page_cache.record(page_cache.app_source_fingerprint(root))

    console.debug(
        f"disk compile cache: reused {len(pages) - len(miss_pages)} page(s), "
        f"recompiled {len(miss_pages)}"
    )
    return True


def _update_manifest_for_misses(
    manifest: dict[str, Any],
    miss_ctx: CompileContext | None,
    miss_pages: Sequence[PageDefinition],
) -> None:
    """Update the on-disk manifest entries for the recompiled pages.

    Args:
        manifest: The loaded manifest (mutated and rewritten).
        miss_ctx: The compile context of the recompiled pages, if any.
        miss_pages: The recompiled page definitions.
    """
    if miss_ctx is None or not miss_pages:
        return
    try:
        all_imports = _deserialize_imports(manifest["all_imports"])
        for page in miss_pages:
            page_ctx = miss_ctx.compiled_pages[page.route]
            manifest["pages"][page.route] = {
                "page_source_fp": page_cache.page_source_fingerprint(page.component),
                "output_path": page_ctx.output_path,
                "output_code": page_ctx.output_code,
                "frontend_imports": _serialize_imports(page_ctx.frontend_imports),
                "app_wrap_keys": _wrap_key_strs(page_ctx.app_wrap_components.keys()),
                "is_stateful": page.route in miss_ctx.stateful_routes,
            }
            all_imports = merge_imports(all_imports, page_ctx.frontend_imports)
        manifest["all_imports"] = _serialize_imports(all_imports)
        _manifest_path().write_text(json.dumps(manifest), encoding="utf-8")
    except Exception as exc:  # best-effort
        console.debug(f"disk compile cache: manifest refresh skipped ({exc!r})")
