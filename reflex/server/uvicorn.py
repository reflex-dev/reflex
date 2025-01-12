"""The UvicornBackendServer."""
# ruff: noqa: RUF009

from __future__ import annotations

# `UvicornBackendServer` defer from other `*BackendServer`, because `uvicorn` he is natively integrated inside the reflex project via Fastapi (same for asyncio)
import asyncio
import os
import ssl
from configparser import RawConfigParser
from dataclasses import dataclass
from typing import IO, Any, Awaitable, Callable

from uvicorn import Config, Server
from uvicorn.config import (
    LOGGING_CONFIG,
    SSL_PROTOCOL_VERSION,
    HTTPProtocolType,
    InterfaceType,
    LifespanType,
    LoopSetupType,
    WSProtocolType,
)

from reflex.constants.base import Env, LogLevel
from reflex.server.base import CliType, CustomBackendServer, field_
from reflex.utils import console


@dataclass
class UvicornBackendServer(CustomBackendServer):
    """Uvicorn backendServer.

    https://www.uvicorn.org/settings/
    """

    host: str = field_(
        default="127.0.0.1", metadata_cli=CliType.default("--host {value}")
    )
    port: int = field_(default=8000, metadata_cli=CliType.default("--port {value}"))
    uds: str | None = field_(
        default=None, metadata_cli=CliType.default("--uds {value}")
    )
    fd: int | None = field_(default=None, metadata_cli=CliType.default("--fd {value}"))
    loop: LoopSetupType = field_(
        default="auto", metadata_cli=CliType.default("--loop {value}")
    )
    http: type[asyncio.Protocol] | HTTPProtocolType = field_(
        default="auto", metadata_cli=CliType.default("--http {value}")
    )
    ws: type[asyncio.Protocol] | WSProtocolType = field_(
        default="auto", metadata_cli=CliType.default("--ws {value}")
    )
    ws_max_size: int = field_(
        default=16777216, metadata_cli=CliType.default("--ws-max-size {value}")
    )
    ws_max_queue: int = field_(
        default=32, metadata_cli=CliType.default("--ws-max-queue {value}")
    )
    ws_ping_interval: float | None = field_(
        default=20.0, metadata_cli=CliType.default("--ws-ping-interval {value}")
    )
    ws_ping_timeout: float | None = field_(
        default=20.0, metadata_cli=CliType.default("--ws-ping-timeout {value}")
    )
    ws_per_message_deflate: bool = field_(
        default=True, metadata_cli=CliType.default("--ws-per-message-deflate {value}")
    )
    lifespan: LifespanType = field_(
        default="auto", metadata_cli=CliType.default("--lifespan {value}")
    )
    env_file: str | os.PathLike[str] | None = field_(
        default=None, metadata_cli=CliType.default("--env-file {value}")
    )
    log_config: dict[str, Any] | str | RawConfigParser | IO[Any] | None = field_(
        default=None,
        default_factory=lambda: LOGGING_CONFIG,
        metadata_cli=CliType.default("--log-config {value}"),
    )
    log_level: str | int | None = field_(
        default=None, metadata_cli=CliType.default("--log-level {value}")
    )
    access_log: bool = field_(
        default=True,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}access-log"),
    )
    use_colors: bool | None = field_(
        default=None,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}use-colors"),
    )
    interface: InterfaceType = field_(
        default="auto", metadata_cli=CliType.default("--interface {value}")
    )
    reload: bool = field_(
        default=False, metadata_cli=CliType.default("--reload {value}")
    )
    reload_dirs: list[str] | str | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload_dir {value}")
    )
    reload_delay: float = field_(
        default=0.25, metadata_cli=CliType.default("--reload-delay {value}")
    )
    reload_includes: list[str] | str | None = field_(
        default=None, metadata_cli=CliType.multiple("----reload-include {value}")
    )
    reload_excludes: list[str] | str | None = field_(
        default=None, metadata_cli=CliType.multiple("--reload-exclude {value}")
    )
    workers: int = field_(default=0, metadata_cli=CliType.default("--workers {value}"))
    proxy_headers: bool = field_(
        default=True,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}proxy-headers"),
    )
    server_header: bool = field_(
        default=True,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}server-header"),
    )
    date_header: bool = field_(
        default=True,
        metadata_cli=CliType.boolean_toggle("--{toggle_kw}{toggle_sep}date-header"),
    )
    forwarded_allow_ips: list[str] | str | None = field_(
        default=None,
        metadata_cli=CliType.multiple("--forwarded-allow-ips {value}", join_sep=","),
    )
    root_path: str = field_(
        default="", metadata_cli=CliType.default("--root-path {value}")
    )
    limit_concurrency: int | None = field_(
        default=None, metadata_cli=CliType.default("--limit-concurrency {value}")
    )
    limit_max_requests: int | None = field_(
        default=None, metadata_cli=CliType.default("--limit-max-requests {value}")
    )
    backlog: int = field_(
        default=2048, metadata_cli=CliType.default("--backlog {value}")
    )
    timeout_keep_alive: int = field_(
        default=5, metadata_cli=CliType.default("--timeout-keep-alive {value}")
    )
    timeout_notify: int = field_(default=30, metadata_cli=None)
    timeout_graceful_shutdown: int | None = field_(
        default=None,
        metadata_cli=CliType.default("--timeout-graceful-shutdown {value}"),
    )
    callback_notify: Callable[..., Awaitable[None]] | None = field_(
        default=None, metadata_cli=None
    )
    ssl_keyfile: str | os.PathLike[str] | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-keyfile {value}")
    )
    ssl_certfile: str | os.PathLike[str] | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-certfile {value}")
    )
    ssl_keyfile_password: str | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-keyfile-password {value}")
    )
    ssl_version: int = field_(
        default=SSL_PROTOCOL_VERSION,
        metadata_cli=CliType.default("--ssl-version {value}"),
    )
    ssl_cert_reqs: int = field_(
        default=ssl.CERT_NONE, metadata_cli=CliType.default("--ssl-cert-reqs {value}")
    )
    ssl_ca_certs: str | None = field_(
        default=None, metadata_cli=CliType.default("--ssl-ca-certs {value}")
    )
    ssl_ciphers: str = field_(
        default="TLSv1", metadata_cli=CliType.default("--ssl-ciphers {value}")
    )
    headers: list[tuple[str, str]] | None = field_(
        default=None,
        metadata_cli=CliType.multiple(
            "--header {value}", value_transformer=lambda value: f"{value[0]}:{value[1]}"
        ),
    )
    factory: bool = field_(
        default=False, metadata_cli=CliType.default("--factory {value}")
    )
    h11_max_incomplete_event_size: int | None = field_(
        default=None,
        metadata_cli=CliType.default("--h11-max-incomplete-event-size {value}"),
    )

    def get_backend_bind(self) -> tuple[str, int]:
        """Return the backend host and port.

        Returns:
            tuple[str, int]: The host address and port.
        """
        return self.host, self.port

    def check_import(self):
        """Check package importation.

        Raises:
            ImportError: raise when some required packaging missing.
        """
        from importlib.util import find_spec

        errors: list[str] = []

        if find_spec("uvicorn") is None:
            errors.append(
                'The `uvicorn` package is required to run `UvicornBackendServer`. Run `pip install "uvicorn>=0.20.0"`.'
            )

        if find_spec("watchfiles") is None and (
            self.reload_includes and self.reload_excludes
        ):
            errors.append(
                'Using `--reload-include` and `--reload-exclude` in `UvicornBackendServer` requires the `watchfiles` extra. Run `pip install "watchfiles>=0.13"`.'
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
        self._app_uri = self.get_app_module(add_extra_api=True)  # type: ignore
        self.log_level = loglevel.value
        self.host = host
        self.port = port
        self._env = env  # type: ignore

        if self.workers == self.get_fields()["workers"].default:
            self.workers = self.get_recommended_workers()
        else:
            if self.workers > (max_workers := self.get_max_workers()):
                self.workers = max_workers

    def run_prod(self) -> list[str]:
        """Run in production mode.

        Returns:
            list[str]: Command ready to be executed
        """
        self.check_import()
        command = ["uvicorn"]

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

        options_ = {
            key: value
            for key, value in self.get_values().items()
            if not self.is_default_value(key, value)
        }

        self._app = Server(  # type: ignore
            config=Config(**options_, app=self._app_uri),
        )
        self._app.run()

    async def shutdown(self):
        """Shutdown the backend server."""
        if self._app and self._env == Env.DEV:
            self._app.shutdown()  # type: ignore
