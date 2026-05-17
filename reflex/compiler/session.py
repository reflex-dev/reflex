"""Python wrapper around the Rust ``CompilerSession``.

The Rust side (``reflex_compiler_rust._native.CompilerSession``) holds the
content-hash compile cache. This wrapper handles:

* A friendly error when the wheel can't be imported.
* Conversion of :mod:`reflex.compiler.ir.builder` lists to msgpack bytes
  (used by tests and benchmarks that still build IR through the Python
  helpers).

The supported caller path is :meth:`CompilerSession.compile_page_from_component`
— the Rust pyread walk over a Component PyObject (plan §0b lever (a)).
The IR-bytes entry points (:meth:`compile_page_ir`, :meth:`compile_app_ir`)
remain available for the codegen-corpus IR-shape tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from reflex.compiler.ir import pack

_WHEEL_MISSING = (
    "reflex_compiler_rust wheel not available — install it via "
    "`maturin develop --release` in packages/reflex-compiler-rust."
)


class CompilerSession:
    """Long-lived compiler handle. Shared across hot-reloads.

    Constructing this is cheap (no compile work happens). The expensive piece
    is the underlying Rust ``CompilerSession`` which holds the content-hash
    cache across calls to :meth:`compile_page` / :meth:`compile_app`.
    """

    def __init__(self) -> None:
        try:
            from reflex_compiler_rust import _native
        except ImportError as exc:
            raise RuntimeError(_WHEEL_MISSING) from exc
        self._inner = _native.CompilerSession()

    # ---- Cache controls -----------------------------------------------------

    def set_cache_capacity(self, cap: int | None) -> None:
        """Bound the in-process page-render cache. ``None`` for unbounded."""
        self._inner.set_cache_capacity(cap)

    def clear_cache(self) -> None:
        self._inner.clear_cache()

    def cache_len(self) -> int:
        return int(self._inner.cache_len())

    # ---- Compile entry points ----------------------------------------------

    def compile_page_ir(self, route_ident: str, page_ir: list) -> str:
        """Compile a pre-built IR tree to a JS source string.

        Args:
            route_ident: JS function name for the page module.
            page_ir: the list-of-lists IR from :mod:`reflex.compiler.ir.builder`.

        Returns:
            Rendered JS source for the page module.
        """
        return self.compile_page_bytes(route_ident, pack.pack_page(page_ir))

    def compile_page_bytes(self, route_ident: str, page_bytes: bytes) -> str:
        """Compile pre-packed IR bytes to a JS source string."""
        return str(self._inner.compile_page(route_ident, page_bytes))

    def compile_page_with_sourcemap(
        self, route_ident: str, page_ir: list
    ) -> tuple[str, list[tuple[int, int, int, int]]]:
        """Compile an IR tree and return ``(js, mappings)``.

        Each mapping is ``(byte_offset, file_id, line, col)``. The cache is
        bypassed — use this for diagnostic flows, not hot-reload.

        Args:
            route_ident: JS function name for the page module.
            page_ir: the list-of-lists IR from :mod:`reflex.compiler.ir.builder`.

        Returns:
            ``(js, mappings)``.
        """
        js, mappings = self._inner.compile_page_with_sourcemap(
            route_ident, pack.pack_page(page_ir)
        )
        return str(js), [tuple(m) for m in mappings]

    def compile_memo_from_component(
        self,
        name: str,
        signature: str,
        component: object,
        *,
        route: str = "/__memo__",
        pre_hooks: str = "",
    ) -> str:
        """Compile a memo wrapper module from a Component PyObject.

        Mirrors :func:`reflex_base.compiler.templates.memo_single_component_template`
        (plan §0b lever (b3)). The Component is expected to already carry
        the ``{children}`` hole at the Python level (a passthrough wrapper
        is e.g. ``rx.box(rx.text(children=...))`` where ``children`` is a
        ``Var(_js_expr='children')`` — see
        :func:`reflex.experimental.memo.create_passthrough_component_memo`).

        Args:
            name: exported memo identifier.
            signature: parameter list spliced after ``memo(``. Use
                ``"{ children }"`` for passthrough wrappers, ``"()"`` for
                snapshot bodies.
            component: the wrapper-component (already hole-substituted).
            route: route value for the harvest pass; defaults to a
                synthetic ``"/__memo__"`` since memos don't have routes.
            pre_hooks: pre-rendered hook block (e.g.
                ``const { resolvedColorMode } = useContext(ColorModeContext)``)
                the Python orchestrator harvested from the memo body via
                ``_get_all_hooks()``. Spliced between the state-context
                hooks and ``return`` inside the memo body. The Rust
                ``state_bindings`` + ``EventLoopContext`` lines are still
                emitted unconditionally; the caller must filter those
                hooks out of ``pre_hooks`` to avoid double-declarations.

        Returns:
            Rendered JS source for the memo module.
        """
        return str(
            self._inner.compile_memo_from_component(
                name, signature, component, route, pre_hooks
            )
        )

    def compile_memo_index(
        self, reexports: list[tuple[str, str]], out_path: str
    ) -> None:
        """Write the memo index module (``.web/utils/components.jsx``).

        Mirrors :func:`reflex_base.compiler.templates.memo_index_template`
        — the small barrel file that re-exports each ``@rx.memo`` custom
        component so ``root.jsx`` can pull them in via
        ``$/utils/components``. The Rust side builds the content and
        writes it to ``out_path`` in one PyO3 call.

        Args:
            reexports: list of ``(export_name, relative_module_specifier)``
                tuples; e.g. ``("Foo", "components/Foo")`` produces
                ``export { Foo } from "components/Foo";``.
            out_path: absolute filesystem path the index gets written
                to. Parent directory must already exist.
        """
        self._inner.compile_memo_index(list(reexports), out_path)

    def compile_styles_root(self, stylesheets: list[str], out_path: str) -> None:
        """Write ``.web/styles/styles.css``.

        Ports :func:`reflex_base.compiler.templates.styles_template`.

        Args:
            stylesheets: stylesheet URLs spliced into ``@import url(...)``
                lines under the single ``@layer __reflex_base;`` header.
            out_path: absolute filesystem path.
        """
        self._inner.compile_styles_root(list(stylesheets), out_path)

    def compile_theme_module(self, theme_js: str, out_path: str) -> None:
        """Write ``.web/utils/theme.js``.

        Ports :func:`reflex_base.compiler.templates.theme_template`. The
        ``theme_js`` argument is the JS object literal Python derives
        from the theme dict via ``LiteralVar.create(theme)``.

        Args:
            theme_js: the JS expression that becomes the default export.
            out_path: absolute filesystem path.
        """
        self._inner.compile_theme_module(theme_js, out_path)

    def compile_app_root_module(
        self,
        imports_str: str,
        dynamic_imports_str: str,
        custom_code_str: str,
        hooks_str: str,
        render_str: str,
        import_window_libraries: str,
        window_imports_str: str,
        out_path: str,
    ) -> None:
        """Write ``.web/app/root.jsx``.

        Ports :func:`reflex_base.compiler.templates.app_root_template`.
        Python pre-renders the dynamic strings (the legacy JSX renderer
        + hooks renderer); Rust splices them into the static layout.

        Args:
            imports_str: rendered ``import …`` lines joined with ``\\n``.
            dynamic_imports_str: rendered dynamic-import statements
                joined with ``\\n``.
            custom_code_str: user-contributed top-level code.
            hooks_str: rendered hook body.
            render_str: rendered JSX expression for the app-wrap chain.
            import_window_libraries: rendered
                ``import * as <alias> from "…"`` lines.
            window_imports_str: rendered ``"<path>": <alias>,`` entries.
            out_path: absolute filesystem path.
        """
        self._inner.compile_app_root_module(
            imports_str,
            dynamic_imports_str,
            custom_code_str,
            hooks_str,
            render_str,
            import_window_libraries,
            window_imports_str,
            out_path,
        )

    def compile_document_root_module(
        self,
        imports_str: str,
        document_render_str: str,
        out_path: str,
    ) -> None:
        """Write ``.web/app/_document.js``.

        Ports :func:`reflex_base.compiler.templates.document_root_template`.

        Args:
            imports_str: rendered ``import …`` lines joined with ``\\n``.
            document_render_str: rendered JSX expression for the
                document tree.
            out_path: absolute filesystem path.
        """
        self._inner.compile_document_root_module(
            imports_str, document_render_str, out_path
        )

    def compile_context_module(
        self,
        is_dev_mode: bool,
        default_color_mode_js: str,
        state_name: str | None,
        state_keys: list[str],
        initial_state_json: str,
        client_storage_json: str,
        out_path: str,
    ) -> None:
        """Write ``.web/utils/context.js``.

        Ports :func:`reflex_base.compiler.templates.context_template`.
        Python pre-serializes the dict inputs (``initial_state``,
        ``client_storage``); Rust assembles the template and writes the
        module.

        Args:
            is_dev_mode: emitted as ``export const isDevMode = …``.
            default_color_mode_js: the JS expression assigned to
                ``defaultColorMode`` (a quoted string or a runtime lookup).
            state_name: full dotted name of the state root; ``None`` for
                the no-state fallback.
            state_keys: full dotted names of every state context.
            initial_state_json: pre-serialized initial-state dict
                (``json_dumps``).
            client_storage_json: pre-serialized client-storage config
                (``json.dumps``).
            out_path: absolute filesystem path.
        """
        self._inner.compile_context_module(
            is_dev_mode,
            default_color_mode_js,
            state_name,
            list(state_keys),
            initial_state_json,
            client_storage_json,
            out_path,
        )

    def compile_stateful_pages_marker(self, routes: list[str], out_path: str) -> None:
        """Write ``.web/backend/stateful_pages.json``.

        Mirrors :meth:`App._write_stateful_pages_marker`. Python decides
        which routes are stateful; Rust serializes the list as JSON and
        writes the file.

        Args:
            routes: stateful route strings (no leading slash).
            out_path: absolute filesystem path.
        """
        self._inner.compile_stateful_pages_marker(list(routes), out_path)

    def should_memoize(self, component: object) -> bool:
        """Run the Rust memoize-decision walk on a Reflex ``Component``.

        Mirrors :func:`reflex.compiler.plugins.memoize._should_memoize`
        — plan §0a phase 2 / §0b lever (b2). Behavior-identical with
        the legacy predicate (parity-tested in
        ``tests/units/compiler/test_memoize_plugin.py``).

        Args:
            component: a ``reflex_base.components.component.BaseComponent``.

        Returns:
            ``True`` iff the component is a memoization candidate.
        """
        return bool(self._inner.should_memoize(component))

    def collect_all_imports(self, component: object) -> dict[str, list]:
        """Rust-merged equivalent of ``Component._get_all_imports()``.

        Walks the Component tree (children + ``_get_components_in_props``),
        calls each node's cached ``_get_imports()``, and merges in a Rust
        ``HashMap`` — drop-in replacement for the Python recursion that
        dominates ``rust_pipeline.compile_pages`` time on import-heavy
        trees.

        The return shape matches ``_get_all_imports`` exactly:
        ``dict[str, list[ImportVar]]`` with no ``$/utils/...`` prefix
        transform. Callers wrap in
        :func:`reflex.compiler.utils.merge_imports` for that step.

        Args:
            component: any ``reflex_base.components.component.BaseComponent``.

        Returns:
            The merged ``ParsedImportDict``.
        """
        return self._inner.collect_all_imports(component)

    def collect_all_imports_into(
        self, target: dict[str, list], component: object
    ) -> None:
        """In-place variant of :meth:`collect_all_imports`.

        Walks ``component``'s tree and appends every entry into
        ``target`` with the ``merge_imports`` ``$/utils/...`` prefix
        transform applied. Use this when accumulating across many
        Components (the ``compile_pages`` page + memo-body loop) so the
        caller doesn't pay the O(N²) cost of rebuilding the outer dict
        on each iteration via Python ``merge_imports``.

        Args:
            target: existing ``ParsedImportDict`` to merge into.
            component: any ``reflex_base.components.component.BaseComponent``.
        """
        self._inner.collect_all_imports_into(target, component)

    def last_phase_timings_ns(self) -> dict[str, int]:
        """Snapshot the Rust per-phase timings from the most recent compile.

        Counters reset at the start of every ``read_page``. Returns
        nanosecond totals keyed by phase name; see the Rust-side doc on
        ``CompilerSession.last_phase_timings_ns`` for the exact phases.

        Returns:
            ``dict[phase_name, ns_total]`` snapshot.
        """
        return self._inner.last_phase_timings_ns()

    def merge_imports_into(
        self, target: dict[str, list], source: dict[str, list]
    ) -> None:
        """Apply the ``merge_imports`` prefix transform to ``source`` in place.

        Same library-prefix rewrite as
        :func:`reflex.compiler.utils.merge_imports` but with no per-entry
        ``isinstance`` dispatch — callers must pass a pre-normalized
        ``ParsedImportDict`` (e.g. from ``parse_imports`` or
        ``_get_all_imports``).

        Args:
            target: existing ``ParsedImportDict`` to merge into.
            source: ``ParsedImportDict`` whose entries get appended.
        """
        self._inner.merge_imports_into(target, source)

    def compile_page_from_component(
        self,
        route_ident: str,
        component: object,
        route: str,
        *,
        title: str | None = None,
        meta_tags: list[tuple[str, str]] | None = None,
        custom_code: list[str] | None = None,
        hooks_body: str | None = None,
    ) -> str:
        """Compile a page directly from a Reflex ``Component`` PyObject.

        The Rust side walks the Component tree via PyO3 ``getattr``
        (``reflex_pyread``, plan §0b lever (a)) and emits JSX in one pass.
        No msgpack hop.

        Args:
            route_ident: JS function name for the page module.
            component: a ``reflex_base.components.component.BaseComponent``.
            route: URL path served by the page.
            title: optional document title.
            meta_tags: optional ``[(name_or_property, content), …]``.
            custom_code: optional component-contributed code blocks
                (``_get_all_custom_code()``) spliced between the import
                section and the ``export default function`` line.
            hooks_body: optional pre-rendered hooks block inserted into
                the component function body after the
                ``useContext(EventLoopContext)`` line.

        Returns:
            Rendered JS source for the page module.
        """
        meta = list(meta_tags) if meta_tags else None
        return str(
            self._inner.compile_page_from_component(
                route_ident,
                component,
                route,
                title,
                meta,
                list(custom_code) if custom_code else None,
                hooks_body,
            )
        )

    def compile_app_ir(
        self,
        pages: Iterable[tuple[str, str, list]],
        *,
        theme: list | None = None,
        global_state: list | None = None,
        plugin_manifest: list | None = None,
    ) -> object:
        """Compile a whole app from IR. Returns the Rust ``CompiledOutput``."""
        packed_pages: Sequence[tuple[str, str, bytes]] = [
            (ident, route, pack.pack_page(page_ir)) for ident, route, page_ir in pages
        ]
        return self._inner.compile_app(
            packed_pages,
            theme=pack.pack_theme(theme) if theme is not None else None,
            global_state=pack.pack_global_state(global_state)
            if global_state is not None
            else None,
            plugin_manifest=pack.pack_plugin_manifest(plugin_manifest)
            if plugin_manifest is not None
            else None,
        )
