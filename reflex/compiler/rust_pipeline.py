"""Drive the Rust compiler from inside Reflex's normal compile lifecycle.

Used by:

* :func:`reflex.reflex.run_rust` — the ``reflex run-rust`` CLI command.
* :mod:`tests` — verifying the swap works on real apps.

Since IR schema v2, the Rust pipeline emits **runtime-compatible** JSX
directly:

* page-level ``component_imports`` (harvested by the Rust pyread walk —
  see plan §0b lever (a)) drive module-scope
  ``import { … } from "<module>"`` lines;
* page-level ``state_bindings`` drive ``useContext(StateContexts.*)`` lines;
* page-level ``needs_ref`` drives the ``useRef`` setup;
* the default exported function name is always ``Component`` — what the
  Reflex React runtime imports.

No Python postprocessor is required. The minimum Python that survives in
``run-rust`` (see plan §0a) is running the user's page callables to
materialize Component trees plus theme-style application; everything from
"I have a Component tree" to "I have a ``.jsx`` file" lives in Rust via
the PyO3 component reader (``reflex_pyread``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from reflex.compiler import utils as compiler_utils
from reflex.compiler.rust_memo import emit_memo_modules, walk_and_memoize
from reflex.compiler.session import CompilerSession


def _route_to_ident(route: str) -> str:
    """Convert a Reflex route into a JS function identifier.

    ``"/"`` → ``"Index"``, ``"/about"`` → ``"About"``,
    ``"/users/[id]"`` → ``"UsersId"``.
    """
    parts = re.findall(r"[A-Za-z0-9]+", route) or ["index"]
    return "".join(p[:1].upper() + p[1:] for p in parts) or "Index"


# Files that must exist for Vite to serve a Reflex app. If all of them are
# present in ``.web/``, the scaffold is ready and ``run-rust`` can drive the
# Rust pipeline straight from ``app._unevaluated_pages``.
_SCAFFOLD_FILES: tuple[str, ...] = (
    "package.json",
    "vite.config.js",
    "reflex.json",
)
_SCAFFOLD_DIRS: tuple[str, ...] = (
    "app",
    "utils",
)


def scaffold_exists(web_dir: Path | None = None) -> bool:
    """Return True if ``.web/`` already has a complete Reflex scaffold.

    A complete scaffold means the npm tree, vite config, and the Reflex
    state/context/utils JS modules are all in place. That's a precondition
    for running ``reflex run-rust`` — if the scaffold is missing, the user
    must run ``reflex init`` / ``reflex run`` once first.

    Args:
        web_dir: Optional override; defaults to ``prerequisites.get_web_dir()``.

    Returns:
        ``True`` when every required scaffold file exists.
    """
    from reflex.utils.prerequisites import get_web_dir

    root = Path(web_dir) if web_dir is not None else Path(get_web_dir())
    if not root.is_dir():
        return False
    if not all((root / f).is_file() for f in _SCAFFOLD_FILES):
        return False
    return all((root / d).is_dir() for d in _SCAFFOLD_DIRS)


def compile_pages(
    app: Any,
    *,
    session: CompilerSession | None = None,
    routes: list[str] | None = None,
) -> tuple[dict[str, Path], Mapping[str, list]]:
    """Compile every registered page through the Rust pipeline.

    Each page goes through:

    1. :func:`reflex.compiler.compiler.compile_unevaluated_page` — Python
       evaluates the page callable, applies recursive theme styles, wraps
       in ``Fragment`` with title + meta. This is the only step Rust can't
       do — it's running user Python that builds the Component tree.
    2. :meth:`CompilerSession.compile_page_from_component` — Rust pyread
       walks the Component tree via PyO3 and emits JSX in one pass.
    3. Write the result to ``.web/app/routes/*.jsx``.

    Alongside JSX emission the function also harvests each evaluated
    page's ``_get_all_imports()`` so callers can hand the merged set to
    :meth:`App._get_frontend_packages` and trigger ``bun install`` without
    running the legacy plugin chain.

    Memoize: per plan §0b lever (b3),
    :func:`reflex.compiler.rust_memo.walk_and_memoize` substitutes memo
    wrappers into each page tree before pyread + emit; unique memo
    bodies are written to ``.web/utils/components/<name>.jsx``. This is
    an MVP — see :mod:`reflex.compiler.rust_memo` for the known gaps vs
    the legacy :class:`MemoizeStatefulPlugin`.

    Args:
        app: a loaded ``rx.App`` whose ``_unevaluated_pages`` is populated.
        session: existing :class:`CompilerSession`. A fresh one is created
            if omitted.
        routes: restrict the compile to these routes. ``None`` (default)
            compiles every registered page.

    Returns:
        ``(written, imports)`` — ``written`` maps each compiled route to
        the path of the emitted JSX file; ``imports`` is the merged
        ``ParsedImportDict`` for the whole compile, suitable to pass to
        :meth:`App._get_frontend_packages`.
    """
    from reflex.compiler import compiler as legacy_compiler
    from reflex.compiler import utils as legacy_utils
    from reflex.compiler.compiler import (
        _apply_common_imports,
        _normalize_library_name,
        _resolve_app_wrap_components,
        _resolve_radix_themes_plugin,
        compile_unevaluated_page,
    )
    from reflex_base.compiler.templates import _RenderUtils, _render_hooks
    from reflex_base.components.dynamic import bundled_libraries
    from reflex_base.config import get_config

    sess = session or CompilerSession()

    # The legacy ``compile_app`` calls ``bundle_library`` for every
    # plugin's ``get_frontend_dependencies()`` so dynamically-loaded
    # libraries end up in ``bundled_libraries`` (which feeds ``root.jsx``'s
    # `window["__reflex"]` mapping). Mirror that side effect so the
    # window-library list matches.
    from reflex_base.components.dynamic import bundle_library, reset_bundled_libraries

    reset_bundled_libraries()
    _, _radix_for_bundle = _resolve_radix_themes_plugin(app, get_config().plugins)
    for plugin in (*get_config().plugins, _radix_for_bundle):
        for dep in plugin.get_frontend_dependencies():
            bundle_library(dep)

    # `@rx.page` decorators populate the ``DECORATED_PAGES`` registry but
    # only get applied to the app inside ``App._compile``. We mimic that
    # here so the "/" route (and any other decorator-registered routes)
    # show up in ``_unevaluated_pages``. Also ensure the 404 page slug
    # is registered — the legacy compile auto-adds it if missing.
    from reflex_base import constants as base_constants

    app._apply_decorated_pages()
    if base_constants.Page404.SLUG not in app._unevaluated_pages:
        app.add_page(route=base_constants.Page404.SLUG)

    written: dict[str, Path] = {}
    all_imports: dict[str, list] = {}
    memo_bodies: dict[str, Any] = {}
    collected_app_wraps: dict[tuple[int, str], Any] = {}
    stateful_routes: list[str] = []
    for route, unev in app._unevaluated_pages.items():
        if routes is not None and route not in routes:
            continue

        # ``compile_unevaluated_page`` evaluates the page callable, applies
        # recursive theme styles, and wraps the root in ``Fragment`` with
        # ``<title>``/``<meta>`` already attached. The bridge sees the wrapped
        # tree and emits the metadata via the IR's component nodes, so we
        # pass ``title=None``/``meta_tags=None`` to ``page_to_ir`` to avoid
        # double-emitting.
        from reflex.state import all_base_state_classes

        n_states_before = len(all_base_state_classes)
        component = compile_unevaluated_page(route, unev, app.style, app.theme)
        if len(all_base_state_classes) > n_states_before:
            # Statefulness detection: matches the legacy plugin
            # (``compile.py:_PageCompiler.compile``) which marks any
            # page whose evaluation registered a new ``BaseState``
            # subclass.
            stateful_routes.append(route)

        # Harvest imports BEFORE memoize substitution: the Rust walker
        # mirrors ``_get_all_imports`` (children + ``_get_components_in_props``)
        # so wrappers haven't yet replaced anything. We need the union so
        # ``bun install`` still pulls in every npm package the original
        # components reference. ``collect_all_imports_into`` mutates
        # ``all_imports`` in place — the previous
        # ``merge_imports(all_imports, ...)`` pattern rebuilt the dict
        # once per page and was O(N²) in cumulative page count.
        sess.collect_all_imports_into(all_imports, component)

        # Harvest app-wrap contributions from every component (Radix
        # ColorMode provider, theme wrap, toaster, etc.). The legacy
        # compile gathers these via `compile_ctx.app_wrap_components`
        # during the plugin walk; we walk the evaluated trees ourselves
        # so `_resolve_app_wrap_components` later produces the full
        # wrapper set.
        collected_app_wraps.update(component._get_all_app_wrap_components())


        # Memoize: substitute wrappers in-place; track each unique memo
        # body for separate emission below.
        component = walk_and_memoize(component, sess, memo_bodies)

        ident = _route_to_ident(route)

        # Harvest custom-code blocks + render hooks for this page —
        # mirrors what the legacy `page_template` splices via
        # `_get_all_custom_code()` + `_render_hooks()`. Without this the
        # rust-emitted page is missing helpers like the markdown
        # ``ComponentMap_*`` closure.
        page_custom_code = list(component._get_all_custom_code())
        page_hooks_body = _render_hooks(component._get_all_hooks())
        rust_js = sess.compile_page_from_component(
            ident,
            component,
            route,
            custom_code=page_custom_code,
            hooks_body=page_hooks_body,
        )

        out_path = Path(compiler_utils.get_page_path(route))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rust_js)
        written[route] = out_path

    # Emit each unique memo body as its own module file. Also harvest
    # each body's imports for the ``bun install`` step.
    components_dir = Path(compiler_utils.get_memo_components_dir())
    for _name, (body, _definition) in memo_bodies.items():
        sess.collect_all_imports_into(all_imports, body)
    emit_memo_modules(memo_bodies, sess, components_dir)

    # Emit `app/root.jsx` — the React Router root module. Python
    # composes the app-wrap chain + renders all the dynamic strings the
    # legacy `app_root_template` expects (imports, hooks, render JSX,
    # window libs); Rust assembles the template.
    # The radix-themes plugin's `compile_page` hook adds the `(20,"Theme")`
    # wrap per page during the legacy compile. We skip the plugin walk
    # but still need the wrap, so add it directly here.
    _, radix_themes_plugin = _resolve_radix_themes_plugin(app, get_config().plugins)
    if radix_themes_plugin.enabled and radix_themes_plugin.theme is not None:
        collected_app_wraps[20, "Theme"] = radix_themes_plugin.theme

    app_wrappers = _resolve_app_wrap_components(app, collected_app_wraps)
    app_root = app._app_root(app_wrappers)
    sess.collect_all_imports_into(all_imports, app_root)

    # Harvest imports from every ``@rx.memo`` custom component for the
    # install step AND emit each component's standalone memo file —
    # sonner / moment / marquee / inkeep / hast-util-to-string all live
    # in custom-component bodies. Must run *after*
    # ``_resolve_app_wrap_components`` since that's where
    # ``memoized_toast_provider`` lazily registers itself in
    # ``CUSTOM_COMPONENTS``.
    #
    # Without re-emitting the per-component files every run, stale
    # ``.web/utils/components/<Name>.jsx`` produced by an older legacy
    # compile would persist — and any Python-side change to the
    # component would leave the on-disk JSX out of sync.
    from reflex_base.components.component import CUSTOM_COMPONENTS

    memo_files, _aggregate_imports = legacy_compiler._compile_memo_components(
        dict.fromkeys(CUSTOM_COMPONENTS.values()),
        (),
    )
    for raw_path, code in memo_files:
        _write(str(legacy_utils.resolve_path_of_web_dir(raw_path)), code)

    for component in dict.fromkeys(CUSTOM_COMPONENTS.values()):
        try:
            _, custom_imports = compiler_utils.compile_custom_component(component)
        except Exception:
            continue
        sess.merge_imports_into(all_imports, custom_imports)

    app_root_imports = app_root._get_all_imports()
    _apply_common_imports(app_root_imports)
    imports_str = "\n".join(
        _RenderUtils.get_import(m)
        for m in compiler_utils.compile_imports(app_root_imports)
    )

    custom_code_str = "\n".join(app_root._get_all_custom_code())
    hooks_str = _render_hooks(app_root._get_all_hooks())
    render_str = _RenderUtils.render(app_root.render())
    dynamic_imports_str = "\n".join(app_root._get_all_dynamic_imports())

    window_libraries = list(
        dict.fromkeys(
            (_normalize_library_name(name), name) for name in bundled_libraries
        )
    )
    import_window_libraries = "\n".join(
        f'import * as {alias} from "{path}";' for alias, path in window_libraries
    )
    window_imports_str = "\n".join(
        f'    "{path}": {alias},' for alias, path in window_libraries
    )

    root_path = str(
        Path(compiler_utils.get_web_dir())
        / base_constants.Dirs.PAGES
        / base_constants.PageNames.APP_ROOT
    )
    Path(root_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_app_root_module(
        imports_str,
        dynamic_imports_str,
        custom_code_str,
        hooks_str,
        render_str,
        import_window_libraries,
        window_imports_str,
        root_path,
    )
    # NB: deliberately not added to `written` — that map is the
    # route → page-file mapping the caller uses for status output, and
    # root.jsx isn't a route.

    # Emit remaining static artifacts the React Router app needs at
    # startup: state contexts, document root, theme, root stylesheet,
    # memo index, and the backend stateful-pages marker. All of these
    # have plugin-walk-free Python emitters we can call directly until
    # they're ported to Rust. See ``scripts/diff_legacy_vs_rust.py`` for
    # the inventory of what's still missing vs the legacy compile.
    _emit_static_artifacts(app, sess, stateful_routes=stateful_routes)

    return written, all_imports


def _emit_static_artifacts(
    app: Any, sess: CompilerSession, *, stateful_routes: list[str] | None = None
) -> None:
    """Emit the non-page static files the React Router app needs at boot.

    The Rust-emitted artifacts go through ``sess.compile_*`` methods
    that stream bytes to disk via ``BufWriter<File>`` — no intermediate
    Python string. The remaining Python-emitter calls are placeholders
    for ports that aren't done yet (``context_template``,
    ``document_root_template``, ``app_root_template``,
    ``styles_template`` — the last one needs the SASS / file-resolution
    refactor in ``_compile_root_stylesheet`` first).
    """
    import json

    from reflex_base.components.component import (
        CUSTOM_COMPONENTS,
        evaluate_style_namespaces,
    )
    from reflex_base.config import get_config
    from reflex_base.constants import Dirs
    from reflex_base.vars.base import LiteralVar

    from reflex_base import constants as base_constants
    from reflex_base.compiler.templates import _RenderUtils, _render_hooks
    from reflex_base.utils.format import json_dumps

    from reflex.compiler import compiler as legacy_compiler
    from reflex.compiler import utils as legacy_utils
    from reflex.compiler.compiler import (
        SYSTEM_COLOR_MODE,
        _normalize_library_name,
        _resolve_radix_themes_plugin,
        _resolve_root_stylesheets,
    )
    from reflex.utils.exec import is_prod_mode
    from reflex.utils.prerequisites import get_backend_dir

    config = get_config()
    app.style = evaluate_style_namespaces(app.style)

    compiler_plugins, radix_themes_plugin = _resolve_radix_themes_plugin(
        app, config.plugins
    )
    radix_theme = radix_themes_plugin.get_theme()

    # ---- utils/context.js (Rust) -----------------------------------------
    # Python still computes the dict inputs (initial state via Pydantic
    # serialization, client storage via a state walk); Rust assembles
    # the template and writes the file. Matches the legacy
    # `_compile_contexts` flow.
    state_root = app._state
    appearance = getattr(radix_theme, "appearance", None)
    if appearance is None or str(LiteralVar.create(appearance)) == '"inherit"':
        appearance = LiteralVar.create(SYSTEM_COLOR_MODE)
    default_color_mode_js = str(appearance)
    is_dev = not is_prod_mode()
    if state_root is not None:
        initial_state = legacy_utils.compile_state(state_root)
        state_name_full = state_root.get_name()
        client_storage = legacy_utils.compile_client_storage(state_root)
        state_keys = list(initial_state.keys())
        initial_state_json = json_dumps(initial_state)
        client_storage_json = json.dumps(client_storage)
    else:
        state_name_full = None
        state_keys = []
        initial_state_json = "{}"
        client_storage_json = "{}"
    ctx_path = legacy_utils.get_context_path()
    Path(ctx_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_context_module(
        is_dev,
        default_color_mode_js,
        state_name_full,
        state_keys,
        initial_state_json,
        client_storage_json,
        ctx_path,
    )

    # ---- app/_document.js (Rust — Python pre-renders the dynamic strings)
    document_root = legacy_utils.create_document_root(
        app.head_components,
        html_lang=app.html_lang,
        html_custom_attrs=(
            {"suppressHydrationWarning": True, **app.html_custom_attrs}
            if app.html_custom_attrs
            else {"suppressHydrationWarning": True}
        ),
    )
    doc_imports = document_root._get_all_imports()
    legacy_compiler._apply_common_imports(doc_imports)
    doc_imports_str = "\n".join(
        _RenderUtils.get_import(m) for m in legacy_utils.compile_imports(doc_imports)
    )
    doc_render_str = _RenderUtils.render(document_root.render())
    doc_path = str(
        Path(compiler_utils.get_web_dir())
        / base_constants.Dirs.PAGES
        / base_constants.PageNames.DOCUMENT_ROOT
    )
    Path(doc_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_document_root_module(doc_imports_str, doc_render_str, doc_path)

    # ---- styles/root stylesheet (Rust) -----------------------------------
    # Python still owns the user-stylesheet resolution + SASS compile
    # (filesystem-heavy, libsass dep) via ``_resolve_root_stylesheets``;
    # Rust just emits the final ``@layer`` + ``@import`` template.
    sheets = _resolve_root_stylesheets(
        app.stylesheets, app.reset_style, plugins=compiler_plugins
    )
    style_path = legacy_utils.get_root_stylesheet_path()
    Path(style_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_styles_root(sheets, style_path)

    # ---- utils/theme.js (Rust) -------------------------------------------
    theme_component = legacy_utils.create_theme(app.style)
    theme_js = str(LiteralVar.create(theme_component))
    theme_path = legacy_utils.get_theme_path()
    Path(theme_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_theme_module(theme_js, theme_path)

    # ---- utils/components.jsx — memo index (Rust) ------------------------
    index_entries: list[tuple[str, str]] = []
    for component in dict.fromkeys(CUSTOM_COMPONENTS.values()):
        try:
            render, _ = compiler_utils.compile_custom_component(component)
        except Exception:
            continue
        name = render["name"]
        index_entries.append((name, legacy_compiler._memo_component_index_specifier(name)))
    index_path = compiler_utils.get_components_path()
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    sess.compile_memo_index(index_entries, index_path)

    # ---- Plugin save tasks (Tailwind config + root style, etc.) ----------
    # Plugins' ``pre_compile`` hook collects "save tasks" — closures that
    # produce ``(path, code)`` tuples for files like ``tailwind.config.js``
    # and ``tailwind.css``. We can't avoid running pre_compile because
    # plugin output is config-dependent (Tailwind scans pages for classes,
    # for example); doing it inline matches the legacy ``compile_app``
    # plugin walk.
    save_tasks: list[tuple] = []
    modify_tasks: list[tuple[str, str, Any]] = []

    def _add_save_task(task_fn, *args, **kwargs):
        save_tasks.append((task_fn, args, kwargs))

    def _make_add_modify_task(plugin):
        plugin_name = plugin.__class__.__module__ + plugin.__class__.__name__

        def _add_modify_task(file_path, modify_fn):
            modify_tasks.append((plugin_name, file_path, modify_fn))

        return _add_modify_task

    for plugin in compiler_plugins:
        plugin.pre_compile(
            add_save_task=_add_save_task,
            add_modify_task=_make_add_modify_task(plugin),
            radix_themes_plugin=radix_themes_plugin,
            unevaluated_pages=list(app._unevaluated_pages.values()),
        )

    # Collect save-task outputs into an ``output_mapping`` first so
    # ``modify_files_tasks`` can transform them in memory before flushing.
    # Matches the legacy ``compile_app`` ordering (save then modify then
    # write) — otherwise a modify-task that depends on the modified file
    # already being on disk would lose changes.
    output_mapping: dict[Path, str] = {}
    for task_fn, args, kwargs in save_tasks:
        result = task_fn(*args, **kwargs)
        if result is None:
            continue
        results = result if isinstance(result, list) else [result]
        for raw_path, code in results:
            resolved = legacy_utils.resolve_path_of_web_dir(raw_path)
            output_mapping[resolved] = code

    for plugin_name, file_path, modify_fn in modify_tasks:
        path = legacy_utils.resolve_path_of_web_dir(file_path)
        content = output_mapping.get(path)
        if content is None:
            if path.exists():
                content = path.read_text()
            else:
                msg = (
                    f"Plugin {plugin_name} tried to modify {path} but it "
                    "does not exist."
                )
                raise FileNotFoundError(msg)
        output_mapping[path] = modify_fn(content)

    for path, code in output_mapping.items():
        _write(str(path), code)

    # ---- backend/stateful_pages.json (Rust) ------------------------------
    # ``stateful_routes`` is computed during the page-evaluation loop in
    # ``compile_pages`` via ``bridge._collect_state_bindings`` — that
    # returns the ``StateContexts.*`` keys each page references, which
    # matches the legacy plugin's "compiling this page introduced a new
    # BaseState" heuristic. Falls back to ``app._stateful_pages`` if not
    # provided (kept for callers that drive ``_emit_static_artifacts``
    # directly).
    backend_dir = Path(get_backend_dir())
    backend_dir.mkdir(parents=True, exist_ok=True)
    routes_list = (
        list(stateful_routes)
        if stateful_routes is not None
        else list(getattr(app, "_stateful_pages", []))
    )
    sess.compile_stateful_pages_marker(
        routes_list,
        str(backend_dir / Dirs.STATEFUL_PAGES),
    )


def _write(path: str, code: str) -> None:
    """Write a compile-output ``(path, code)`` tuple to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(code)
