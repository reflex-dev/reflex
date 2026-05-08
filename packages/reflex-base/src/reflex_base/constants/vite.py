"""Vite Config constants."""

from collections.abc import Sequence
from typing import Any, Literal, TypedDict

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var


class Alias(TypedDict):
    """Configuration for module path aliases in Vite.

    Attributes:
        find: The module path pattern to find and replace.
        replacement: The replacement path for the matched pattern.
    """

    find: str | Var
    replacement: str | Var


class Resolve(TypedDict, total=False):
    """Configuration options for Vite module resolution.

    Attributes:
        alias: List of module path aliases for resolution.
        dedupe: List of packages to dedupe or raw JS configuration.
        conditions: List of export conditions for module resolution.
        mainFields: List of main fields to check during resolution.
        extensions: List of file extensions to resolve.
        preserveSymlinks: Whether to preserve symbolic links during resolution.
    """

    alias: list[Alias]
    dedupe: list[str] | Var
    conditions: list[str] | Var
    mainFields: list[str] | Var
    extensions: list[str] | Var
    preserveSymlinks: bool | Var


class HTML(TypedDict, total=False):
    """Configuration options for HTML handling in Vite.

    Attributes:
        cspNonce: Content Security Policy nonce for inline scripts and styles.
    """

    cspNonce: str | Var


class CSS(TypedDict, total=False):
    """Configuration options for CSS handling in Vite.

    Attributes:
        postcss: PostCSS configuration or plugin path.
        preprocessorOptions: Options for CSS preprocessors like Sass, Less, etc.
        preprocessorMaxWorkers: Maximum number of preprocessor workers or True for auto.
    """

    postcss: str | Var
    preprocessorOptions: dict[str, Any] | Var
    preprocessorMaxWorkers: int | Literal[True] | Var


class Json(TypedDict, total=False):
    """Configuration options for JSON handling in Vite.

    Attributes:
        namedExports: Whether to enable named exports for JSON imports.
        stringify: Whether to stringify JSON or use automatic handling.
    """

    namedExports: bool | Var
    stringify: bool | Literal["auto"] | Var


class HTTPSOptions(TypedDict):
    """Configuration options for HTTPS settings.

    Attributes:
        key: The private key for HTTPS configuration.
        cert: The certificate for HTTPS configuration.
    """

    key: str | Var
    cert: str | Var


class HMROptions(TypedDict, total=False):
    """Configuration options for Vite Hot Module Replacement (HMR).

    Attributes:
        protocol: The protocol to use for HMR connection.
        host: The host for HMR server.
        port: The port for HMR server.
        path: The path for HMR WebSocket connection.
        timeout: Timeout for HMR connection in milliseconds.
        overlay: Whether to show HMR error overlay.
        clientPort: The port for HMR client connection.
    """

    protocol: str | Var
    host: str | Var
    port: int | Var
    path: str | Var
    timeout: int | Var
    overlay: bool | Var
    clientPort: int | Var


class WarmupOptions(TypedDict, total=False):
    """Configuration options for Vite warmup settings.

    Attributes:
        clientFiles: List of client files to warmup.
        ssrFiles: List of SSR files to warmup.
    """

    clientFiles: list[str] | Var
    ssrFiles: list[str] | Var


class ServerFsOptions(TypedDict, total=False):
    """Configuration options for Vite server file system settings.

    Attributes:
        strict: Whether to enforce strict file system rules.
        allow: List of paths that are allowed to be served.
        deny: List of paths that are denied from being served.
    """

    strict: bool | Var
    allow: list[str] | Var
    deny: list[str] | Var


class Server(TypedDict, total=False):
    """Configuration options for Vite development server.

    Attributes:
        host: The host to bind the server to.
        allowedHosts: List of allowed hosts or True to allow all.
        port: The port number for the development server.
        strictPort: Whether to use strict port binding.
        https: HTTPS configuration options.
        open: Whether to open browser or specify URL to open.
        proxy: Proxy configuration for the development server.
        cors: CORS configuration settings.
        headers: Custom headers to send with responses.
        hmr: Hot Module Replacement configuration.
        warmup: Warmup configuration options.
        watch: File watching configuration.
        middlewareMode: Whether to run in middleware mode.
        fs: File system configuration options.
        origin: Origin URL for the server.
        sourcemapIgnoreList: Sourcemap ignore list configuration.
    """

    host: str | bool | Var
    allowedHosts: list[str] | bool | Var
    port: int | Var
    strictPort: bool | Var
    https: HTTPSOptions
    open: bool | str | Var
    proxy: dict[str, Any] | Var
    cors: bool | dict[str, Any] | Var
    headers: dict[str, str] | Var
    hmr: bool | HMROptions
    warmup: WarmupOptions
    watch: dict[str, Any] | Var | None
    middlewareMode: bool | Var
    fs: ServerFsOptions
    origin: str | Var
    sourcemapIgnoreList: Literal[False] | Var


class ModulePreloadOptions(TypedDict, total=False):
    """Configuration options for Vite module preload settings.

    Attributes:
        polyfill: Whether to polyfill module preload functionality.
        resolveDependencies: Custom function for resolving dependencies.
    """

    polyfill: bool | Var
    resolveDependencies: Var


class BuildLibOptions(TypedDict, total=False):
    """Configuration options for Vite library build settings.

    Attributes:
        entry: Entry point(s) for the library build.
        name: Name of the library for UMD/IIFE builds.
        formats: Output formats for the library build.
        fileName: Custom filename pattern for output files.
        cssFileName: Custom filename pattern for CSS files.
    """

    entry: str | list[str] | Var
    name: str | Var
    formats: list[Literal["es", "cjs", "umd", "iife"]] | Var
    fileName: str | Var
    cssFileName: str | Var


class BuildOptions(TypedDict, total=False):
    """Configuration options for Vite build settings.

    Attributes:
        target: Build target(s) for the output bundle.
        modulePreload: Module preload configuration options.
        polyfillModulePreload: Whether to polyfill module preload.
        outDir: Output directory for build files.
        assetsDir: Directory for static assets within outDir.
        assetsInlineLimit: Size limit for inlining assets as base64.
        cssCodeSplit: Whether to enable CSS code splitting.
        cssTarget: CSS build target(s).
        cssMinify: CSS minification method or boolean.
        sourcemap: Sourcemap generation options.
        rollupOptions: Additional Rollup configuration.
        commonjsOptions: CommonJS plugin options.
        dynamicImportVarsOptions: Dynamic import variables options.
        lib: Library build configuration.
        manifest: Whether to generate build manifest.
        ssrManifest: Whether to generate SSR manifest.
        ssr: SSR build configuration.
        emitAssets: Whether to emit assets during build.
        ssrEmitAssets: Whether to emit assets during SSR build.
        minify: Minification method or boolean.
        terserOptions: Terser minification options.
        write: Whether to write files to disk.
        emptyOutDir: Whether to empty output directory before build.
        copyPublicDir: Whether to copy public directory.
        reportCompressedSize: Whether to report compressed bundle sizes.
        chunkSizeWarningLimit: Warning threshold for chunk sizes in bytes.
        watch: File watching configuration for build mode.
    """

    target: str | list[str] | Var
    modulePreload: bool | ModulePreloadOptions | Var
    polyfillModulePreload: bool | Var
    outDir: str | Var
    assetsDir: str | Var
    assetsInlineLimit: int | Var
    cssCodeSplit: bool | Var
    cssTarget: str | list[str] | Var
    cssMinify: bool | Literal["esbuild", "lightningcss"] | Var
    sourcemap: bool | Literal["inline", "hidden"] | Var
    rollupOptions: dict[str, Any] | Var
    commonjsOptions: dict[str, Any] | Var
    dynamicImportVarsOptions: dict[str, Any] | Var
    lib: BuildLibOptions
    manifest: bool | str | Var
    ssrManifest: bool | str | Var
    ssr: bool | str | Var
    emitAssets: bool | Var
    ssrEmitAssets: bool | Var
    minify: bool | Literal["terser", "esbuild"] | Var
    terserOptions: dict[str, Any] | Var
    write: bool | Var
    emptyOutDir: bool | Var
    copyPublicDir: bool | Var
    reportCompressedSize: bool | Var
    chunkSizeWarningLimit: int | Var
    watch: dict[str, Any] | Var | None


class PreviewOptions(TypedDict, total=False):
    """Configuration options for Vite preview server.

    Attributes:
        host: The host to bind the preview server to.
        allowedHosts: List of allowed hosts or True to allow all.
        port: The port number for the preview server.
        strictPort: Whether to use strict port binding.
        https: HTTPS configuration options.
        open: Whether to open browser or specify URL to open.
        proxy: Proxy configuration for the preview server.
        cors: CORS configuration settings.
        headers: Custom headers to send with responses.
    """

    host: str | bool | Var
    allowedHosts: list[str] | Literal[True] | Var
    port: int | Var
    strictPort: bool | Var
    https: HTTPSOptions
    open: bool | str | Var
    proxy: dict[str, Any] | Var
    cors: bool | dict[str, Any] | Var
    headers: dict[str, str] | Var


class OptimizeDepsOptions(TypedDict, total=False):
    """Configuration options for Vite dependency optimization.

    Attributes:
        entries: Entry points for dependency optimization.
        exclude: Dependencies to exclude from optimization.
        include: Dependencies to include in optimization.
        esbuildOptions: Additional esbuild configuration options.
        force: Whether to force re-optimization of dependencies.
        noDiscovery: Whether to disable automatic dependency discovery.
        holdUntilCrawlEnd: Whether to hold optimization until crawl completion.
        disabled: Whether to disable dependency optimization entirely.
    """

    entries: str | list[str] | Var
    exclude: list[str] | Var
    include: list[str] | Var
    esbuildOptions: dict[str, Any] | Var
    force: bool | Var
    noDiscovery: bool | Var
    holdUntilCrawlEnd: bool | Var
    disabled: bool | Literal["build", "dev"] | Var


class SSRResolveOptions(TypedDict, total=False):
    """Configuration options for SSR module resolution in Vite.

    Attributes:
        conditions: List of conditions for module resolution.
        externalConditions: List of external conditions for module resolution.
        mainFields: List of main fields to check for module resolution.
    """

    conditions: list[str] | Var
    externalConditions: list[str] | Var
    mainFields: list[str] | Var


class SSROptions(TypedDict, total=False):
    """Configuration options for Server-Side Rendering (SSR) in Vite.

    Attributes:
        external: External dependencies to be excluded from bundling.
        noExternal: Dependencies that should not be externalized.
        target: The SSR build target environment.
        resolve: SSR-specific module resolution options.
    """

    external: list[str] | bool | Var
    noExternal: str | list[str] | Literal[True] | Var
    target: Literal["node", "webworker"]
    resolve: SSRResolveOptions


class WorkerOptions(TypedDict, total=False):
    """Configuration options for Vite worker build settings.

    Attributes:
        format: The output format for workers ("es" or "iife").
        plugins: Raw JavaScript plugins configuration.
        rollupOptions: Additional rollup configuration options.
    """

    format: Literal["es", "iife"]
    plugins: Var
    rollupOptions: dict[str, Any]


class ViteConfigDict(TypedDict, total=False):
    """Configuration options for Vite build tool.

    This TypedDict defines the structure for Vite configuration options,
    allowing partial specification of build settings, server options,
    and other Vite-related configurations.

    Additional imports and user-defined functions can be passed, which are handled explicitly and differently
    compared to the rest of the standard Vite config options.
    """

    plugins: list[Var]
    root: str | Var
    base: str | Var
    mode: Literal["development", "production"] | Var
    define: dict[str, str | Var] | Var
    publicDir: str | Literal[False] | Var
    cacheDir: str | Var
    resolve: Resolve
    html: HTML
    css: CSS
    json: Json
    server: Server
    build: BuildOptions
    preview: PreviewOptions
    optimizeDeps: OptimizeDepsOptions
    ssr: SSROptions
    worker: WorkerOptions
    experimental: dict

    # Additional not defined by Vite
    imports: dict[str, ImportVar | Sequence[ImportVar]]
    functions: list[Var]
