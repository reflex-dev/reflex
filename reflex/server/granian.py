"""The GranianBackendServer."""
# ruff: noqa: RUF009

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any, Literal

from reflex.constants.base import Env, LogLevel
from reflex.server.base import CliType, CustomBackendServer, field_
from reflex.utils import console


@dataclass
class HTTP1Settings:
    """Granian HTTP1Settings."""

    # https://github.com/emmett-framework/granian/blob/261ceba3fd93bca10300e91d1498bee6df9e3576/granian/http.py#L6
    keep_alive: bool = dc_field(default=True)
    max_buffer_size: int = dc_field(default=8192 + 4096 * 100)
    pipeline_flush: bool = dc_field(default=False)


@dataclass
class HTTP2Settings:  # https://github.com/emmett-framework/granian/blob/261ceba3fd93bca10300e91d1498bee6df9e3576/granian/http.py#L13
    """Granian HTTP2Settings."""

    adaptive_window: bool = dc_field(default=False)
    initial_connection_window_size: int = dc_field(default=1024 * 1024)
    initial_stream_window_size: int = dc_field(default=1024 * 1024)
    keep_alive_interval: int | None = dc_field(default=None)
    keep_alive_timeout: int = dc_field(default=20)
    max_concurrent_streams: int = dc_field(default=200)
    max_frame_size: int = dc_field(default=1024 * 16)
    max_headers_size: int = dc_field(default=16 * 1024 * 1024)
    max_send_buffer_size: int = dc_field(default=1024 * 400)


@dataclass
class GranianBackendServer(CustomBackendServer):
    """Granian backendServer.

    https://github.com/emmett-framework/granian/blob/fc11808ed177362fcd9359a455a733065ddbc505/granian/cli.py#L52 (until Granian has the proper documentation)

    """

    address: str = field_(
        default="127.0.0.1", metadata_cli=CliType.default("--host {value}")
    )
    port: int = field_(default=8000, metadata_cli=CliType.default("--port {value}"))
    interface: Literal["asgi", "asginl", "rsgi", "wsgi"] = field_(
        default="rsgi", metadata_cli=CliType.default("--interface {value}")
    )
    workers: int = field_(default=0, metadata_cli=CliType.default("--workers {value}"))
    threads: int = field_(default=0, metadata_cli=CliType.default("--threads {value}"))
    blocking_threads: int | None = field_(
        default=None, metadata_cli=CliType.default("--blocking-threads {value}")
    )
    threading_mode: Literal["runtime", "workers"] = field_(
        default="workers", metadata_cli=CliType.default("--threading-mode {value}")
    )
    loop: Literal["auto", "asyncio", "uvloop"] = field_(
        default="auto", metadata_cli=CliType.default("--loop {value}")
    )
    loop_opt: bool = field_(
        default=False,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}opt"),
    )
    http: Literal["auto", "1", "2"] = field_(
        default="auto", metadata_cli=CliType.default("--http {value}")
    )
    websockets: bool = field_(
        default=True, metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}ws")
    )
    backlog: int = field_(
        default=1024, metadata_cli=CliType.default("--backlog {value}")
    )
    backpressure: int | None = field_(
        default=None, metadata_cli=CliType.default("--backpressure {value}")
    )
    http1_keep_alive: bool = field_(
        default=True, metadata_cli=CliType.default("--http1-keep-alive {value}")
    )
    http1_max_buffer_size: int = field_(
        default=417792, metadata_cli=CliType.default("--http1-max-buffer-size {value}")
    )
    http1_pipeline_flush: bool = field_(
        default=False, metadata_cli=CliType.default("--http1-pipeline-flush {value}")
    )
    http2_adaptive_window: bool = field_(
        default=False, metadata_cli=CliType.default("--http2-adaptive-window {value}")
    )
    http2_initial_connection_window_size: int = field_(
        default=1048576,
        metadata_cli=CliType.default("--http2-initial-connection-window-size {value}"),
    )
    http2_initial_stream_window_size: int = field_(
        default=1048576,
        metadata_cli=CliType.default("--http2-initial-stream-window-size {value}"),
    )
    http2_keep_alive_interval: int | None = field_(
        default=None,
        metadata_cli=CliType.default("--http2-keep-alive-interval {value}"),
    )
    http2_keep_alive_timeout: int = field_(
        default=20, metadata_cli=CliType.default("--http2-keep-alive-timeout {value}")
    )
    http2_max_concurrent_streams: int = field_(
        default=200,
        metadata_cli=CliType.default("--http2-max-concurrent-streams {value}"),
    )
    http2_max_frame_size: int = field_(
        default=16384, metadata_cli=CliType.default("--http2-max-frame-size {value}")
    )
    http2_max_headers_size: int = field_(
        default=16777216,
        metadata_cli=CliType.default("--http2-max-headers-size {value}"),
    )
    http2_max_send_buffer_size: int = field_(
        default=409600,
        metadata_cli=CliType.default("--http2-max-send-buffer-size {value}"),
    )
    log_enabled: bool = field_(
        default=True,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}log"),
    )
    log_level: Literal["critical", "error", "warning", "warn", "info", "debug"] = (
        field_(default="info", metadata_cli=CliType.default("--log-level {value}"))
    )
    log_dictconfig: dict[str, Any] | None = field_(default=None, metadata_cli=None)
    log_access: bool = field_(
        default=False,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}log-access"),
    )
    log_access_format: str | None = field_(
        default=None, metadata_cli=CliType.default("--access-log-fmt {value}")
    )
    ssl_cert: Path | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-certificate {value}")
    )
    ssl_key: Path | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-keyfile {value}")
    )
    ssl_key_password: str | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-keyfile-password {value}")
    )
    url_path_prefix: str | None = field_(
        default=None, metadata_cli=CliType.default("--url-path-prefix {value}")
    )
    respawn_failed_workers: bool = field_(
        default=False,
        metadata_cli=CliType.boolean_toggle(
            "--{toggle_kw}{toggle_sep}respawn-failed-workers"
        ),
    )
    respawn_interval: float = field_(
        default=3.5, metadata_cli=CliType.default("--respawn-interval {value}")
    )
    workers_lifetime: int | None = field_(
        default=None, metadata_cli=CliType.default("--workers-lifetime {value}")
    )
    factory: bool = field_(
        default=False,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}factory"),
    )
    reload: bool = field_(
        default=False,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}reload"),
    )
    reload_paths: list[Path] | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload-paths {value}")
    )
    reload_ignore_dirs: list[str] | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload-ignore-dirs {value}")
    )
    reload_ignore_patterns: list[str] | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload-ignore-patterns {value}")
    )
    reload_ignore_paths: list[Path] | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload-ignore-paths {value}")
    )
    reload_filter: object | None = field_(  # type: ignore
        default=None, metadata_cli=None
    )
    process_name: str | None = field_(
        default=None, metadata_cli=CliType.default("--process-name {value}")
    )
    pid_file: Path | None = field_(
        default=None, metadata_cli=CliType.default("--pid-file {value}")
    )

    def get_backend_bind(self) -> tuple[str, int]:
        """Return the backend host and port.

        Returns:
            tuple[str, int]: The host address and port.
        """
        return self.address, self.port

    def check_import(self):
        """Check package importation.

        Raises:
            ImportError: raise when some required packaging missing.
        """
        from importlib.util import find_spec

        errors: list[str] = []

        if find_spec("granian") is None:
            errors.append(
                'The `granian` package is required to run `GranianBackendServer`. Run `pip install "granian>=1.6.0"`.'
            )

        if find_spec("watchfiles") is None and self.reload:
            errors.append(
                'Using `--reload` in `GranianBackendServer` requires the `watchfiles` extra. Run `pip install "watchfiles~=0.21"`.'
            )

        if errors:
            console.error("\n".join(errors))
            raise ImportError()

    def setup(self, host: str, port: int, loglevel: LogLevel, env: Env):
        """Setup.

        Args:
            host (str): host address
            port (int): port address
            loglevel (LogLevel): log level
            env (Env): prod/dev environment
        """
        self.check_import()
        self._app_uri = self.get_app_module(for_granian_target=True, add_extra_api=True)  # type: ignore
        self.log_level = loglevel.value  # type: ignore
        self.address = host
        self.port = port
        self.interface = "asgi"  # NOTE: prevent obvious error
        self._env = env  # type: ignore

        if self.workers == self.get_fields()["workers"].default:
            self.workers = self.get_recommended_workers()
        else:
            if self.workers > (max_workers := self.get_max_workers()):
                self.workers = max_workers

        if self.threads == self.get_fields()["threads"].default:
            self.threads = self.get_recommended_threads()
        else:
            if self.threads > (max_threads := self.get_max_threads()):
                self.threads = max_threads

    def run_prod(self):
        """Run in production mode.

        Returns:
            list[str]: Command ready to be executed
        """
        self.check_import()
        command = ["granian"]

        for key, field in self.get_fields().items():
            if (
                field.metadata["exclude"] is False
                and field.metadata["cli"]
                and not self.is_default_value(key, (value := getattr(self, key)))
            ):
                command += field.metadata["cli"](value).split(" ")

        return [*command, self._app_uri]

    def run_dev(self):
        """Run in development mode."""
        self.check_import()
        from granian import Granian  # type: ignore

        exclude_keys = (
            "http1_keep_alive",
            "http1_max_buffer_size",
            "http1_pipeline_flush",
            "http2_adaptive_window",
            "http2_initial_connection_window_size",
            "http2_initial_stream_window_size",
            "http2_keep_alive_interval",
            "http2_keep_alive_timeout",
            "http2_max_concurrent_streams",
            "http2_max_frame_size",
            "http2_max_headers_size",
            "http2_max_send_buffer_size",
        )

        self._app = Granian(  # type: ignore
            **{
                **{
                    key: value
                    for key, value in self.get_values().items()
                    if (
                        key not in exclude_keys
                        and not self.is_default_value(key, value)
                    )
                },
                "target": self._app_uri,
                "http1_settings": HTTP1Settings(
                    self.http1_keep_alive,
                    self.http1_max_buffer_size,
                    self.http1_pipeline_flush,
                ),
                "http2_settings": HTTP2Settings(
                    self.http2_adaptive_window,
                    self.http2_initial_connection_window_size,
                    self.http2_initial_stream_window_size,
                    self.http2_keep_alive_interval,
                    self.http2_keep_alive_timeout,
                    self.http2_max_concurrent_streams,
                    self.http2_max_frame_size,
                    self.http2_max_headers_size,
                    self.http2_max_send_buffer_size,
                ),
            }
        )
        self._app.serve()

    async def shutdown(self):
        """Shutdown the backend server."""
        if self._app and self._env == Env.DEV:
            self._app.shutdown()
