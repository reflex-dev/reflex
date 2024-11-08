"""The GranianBackendServer."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any, Literal, Type

from reflex.constants.base import Env, LogLevel
from reflex.server.base import CustomBackendServer
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


try:
    import watchfiles  # type: ignore
except ImportError:
    watchfiles = None

_mapping_attr_to_cli: dict[str, str] = {
    "address": "--host",
    "port": "--port",
    "interface": "--interface",
    "http": "--http",
    "websockets": "--ws",  # NOTE: when `websockets` True: `--ws`; False: `--no-ws`
    "workers": "--workers",
    "threads": "--threads",
    "blocking_threads": "--blocking-threads",
    "threading_mode": "--threading-mode",
    "loop": "--loop",
    "loop_opt": "--opt",  # NOTE: when `loop_opt` True: `--opt`; False: `--no-opt`
    "backlog": "--backlog",
    "backpressure": "--backpressure",
    "http1_keep_alive": "--http1-keep-alive",
    "http1_max_buffer_size": "--http1-max-buffer-size",
    "http1_pipeline_flush": "--http1-pipeline-flush",
    "http2_adaptive_window": "--http2-adaptive-window",
    "http2_initial_connection_window_size": "--http2-initial-connection-window-size",
    "http2_initial_stream_window_size": "--http2-initial-stream-window-size",
    "http2_keep_alive_interval": "--http2-keep-alive-interval",
    "http2_keep_alive_timeout": "--http2-keep-alive-timeout",
    "http2_max_concurrent_streams": "--http2-max-concurrent-streams",
    "http2_max_frame_size": "--http2-max-frame-size",
    "http2_max_headers_size": "--http2-max-headers-size",
    "http2_max_send_buffer_size": "--http2-max-send-buffer-size",
    "log_enabled": "--log",  # NOTE: when `log_enabled` True: `--log`; False: `--no-log`
    "log_level": "--log-level",
    "log_access": "--log-access",  # NOTE: when `log_access` True: `--log-access`; False: `--no-log-access`
    "log_access_format": "--access-log-fmt",
    "ssl_cert": "--ssl-certificate",
    "ssl_key": "--ssl-keyfile",
    "ssl_key_password": "--ssl-keyfile-password",
    "url_path_prefix": "--url-path-prefix",
    "respawn_failed_workers": "--respawn-failed-workers",  # NOTE: when `respawn_failed_workers` True: `--respawn-failed-workers`; False: `--no-respawn-failed-workers`
    "respawn_interval": "--respawn-interval",
    "workers_lifetime": "--workers-lifetime",
    "factory": "--factory",  # NOTE: when `factory` True: `--factory`; False: `--no-factory`
    "reload": "--reload",  # NOTE: when `reload` True: `--reload`; False: `--no-reload`
    "reload_paths": "--reload-paths",
    "reload_ignore_dirs": "--reload-ignore-dirs",
    "reload_ignore_patterns": "--reload-ignore-patterns",
    "reload_ignore_paths": "--reload-ignore-paths",
    "process_name": "--process-name",
    "pid_file": "--pid-file",
}


class GranianBackendServer(CustomBackendServer):
    """Granian backendServer."""

    # https://github.com/emmett-framework/granian/blob/fc11808ed177362fcd9359a455a733065ddbc505/granian/server.py#L69

    target: str | None = None
    address: str = "127.0.0.1"
    port: int = 8000
    interface: Literal["asgi", "asginl", "rsgi", "wsgi"] = "rsgi"
    workers: int = 0
    threads: int = 0
    blocking_threads: int | None = None
    threading_mode: Literal["runtime", "workers"] = "workers"
    loop: Literal["auto", "asyncio", "uvloop"] = "auto"
    loop_opt: bool = False
    http: Literal["auto", "1", "2"] = "auto"
    websockets: bool = True
    backlog: int = 1024
    backpressure: int | None = None

    # http1_settings: HTTP1Settings | None = None
    # NOTE: child of http1_settings, needed only for cli mode
    http1_keep_alive: bool = HTTP1Settings.keep_alive
    http1_max_buffer_size: int = HTTP1Settings.max_buffer_size
    http1_pipeline_flush: bool = HTTP1Settings.pipeline_flush

    # http2_settings: HTTP2Settings | None = None
    # NOTE: child of http2_settings, needed only for cli mode
    http2_adaptive_window: bool = HTTP2Settings.adaptive_window
    http2_initial_connection_window_size: int = (
        HTTP2Settings.initial_connection_window_size
    )
    http2_initial_stream_window_size: int = HTTP2Settings.initial_stream_window_size
    http2_keep_alive_interval: int | None = HTTP2Settings.keep_alive_interval
    http2_keep_alive_timeout: int = HTTP2Settings.keep_alive_timeout
    http2_max_concurrent_streams: int = HTTP2Settings.max_concurrent_streams
    http2_max_frame_size: int = HTTP2Settings.max_frame_size
    http2_max_headers_size: int = HTTP2Settings.max_headers_size
    http2_max_send_buffer_size: int = HTTP2Settings.max_send_buffer_size

    log_enabled: bool = True
    log_level: Literal["critical", "error", "warning", "warn", "info", "debug"] = "info"
    log_dictconfig: dict[str, Any] | None = None
    log_access: bool = False
    log_access_format: str | None = None
    ssl_cert: Path | None = None
    ssl_key: Path | None = None
    ssl_key_password: str | None = None
    url_path_prefix: str | None = None
    respawn_failed_workers: bool = False
    respawn_interval: float = 3.5
    workers_lifetime: int | None = None
    factory: bool = False
    reload: bool = False
    reload_paths: list[Path] | None = None
    reload_ignore_dirs: list[str] | None = None
    reload_ignore_patterns: list[str] | None = None
    reload_ignore_paths: list[Path] | None = None
    reload_filter: Type[getattr(watchfiles, "BaseFilter", None)] | None = None  # type: ignore
    process_name: str | None = None
    pid_file: Path | None = None

    def check_import(self, extra: bool = False):
        """Check package importation."""
        from importlib.util import find_spec

        errors: list[str] = []

        if find_spec("granian") is None:
            errors.append(
                'The `granian` package is required to run `GranianBackendServer`. Run `pip install "granian>=1.6.0"`.'
            )

        if find_spec("watchfiles") is None and extra:
            # NOTE: the `\[` is for force `rich.Console` to not consider it like a color or anything else which he not printing `[.*]`
            errors.append(
                r'Using --reload in `GranianBackendServer` requires the granian\[reload] extra. Run `pip install "granian\[reload]>=1.6.0"`.'
            )  # type: ignore

        if errors:
            console.error("\n".join(errors))
            sys.exit()

    def setup(self, host: str, port: int, loglevel: LogLevel, env: Env):
        """Setup."""
        self.target = self.get_app_module(for_granian_target=True, add_extra_api=True)
        self.log_level = loglevel.value  # type: ignore
        self.address = host
        self.port = port
        self.interface = "asgi"  # prevent obvious error

        if env == Env.PROD:
            if self.workers == self.get_fields()["workers"].default:
                self.workers = self.get_recommended_workers()
            else:
                if self.workers > (max_threads := self.get_max_workers()):
                    self.workers = max_threads

            if self.threads == self.get_fields()["threads"].default:
                self.threads = self.get_recommended_threads()
            else:
                if self.threads > (max_threads := self.get_max_threads()):
                    self.threads = max_threads

        if env == Env.DEV:
            from reflex.config import get_config  # prevent circular import

            self.reload = True
            self.reload_paths = [Path(get_config().app_name)]
            self.reload_ignore_dirs = [".web"]

    def run_prod(self):
        """Run in production mode."""
        self.check_import()
        command = ["granian"]

        for key, field in self.get_fields().items():
            if key != "target":
                value = getattr(self, key)
                if _mapping_attr_to_cli.get(key) and value != field.default:
                    if isinstance(value, list):
                        for v in value:
                            command += [_mapping_attr_to_cli[key], str(v)]
                    elif isinstance(value, bool):
                        command.append(
                            f"--{'no-' if value is False else ''}{_mapping_attr_to_cli[key][2:]}"
                        )
                    else:
                        command += [_mapping_attr_to_cli[key], str(value)]

        return command + [
            self.get_app_module(for_granian_target=True, add_extra_api=True)
        ]

    def run_dev(self):
        """Run in development mode."""
        self.check_import(extra=self.reload)
        from granian import Granian

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
        model = self.get_fields()
        Granian(
            **{
                **{
                    key: value
                    for key, value in self.dict().items()
                    if key not in exclude_keys and value != model[key].default
                },
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
        ).serve()
