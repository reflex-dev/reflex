"""The GunicornBackendServer."""
# ruff: noqa: RUF009

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from reflex.constants.base import IS_WINDOWS, Env, LogLevel
from reflex.server.base import CliType, CustomBackendServer, field_
from reflex.utils import console


@dataclass
class GunicornBackendServer(CustomBackendServer):
    """Gunicorn backendServer.

    https://docs.gunicorn.org/en/latest/settings.html
    """

    config: str = field_(
        default="./gunicorn.conf.py", metadata_cli=CliType.default("--config {value}")
    )
    bind: list[str] = field_(
        default=None,
        default_factory=lambda: ["127.0.0.1:8000"],
        metadata_cli=CliType.multiple("--bind {value}"),
    )
    backlog: int = field_(
        default=2048, metadata_cli=CliType.default("--backlog {value}")
    )
    workers: int = field_(default=0, metadata_cli=CliType.default("--workers {value}"))
    worker_class: Literal[
        "sync",
        "eventlet",
        "gevent",
        "tornado",
        "gthread",
        "uvicorn.workers.UvicornH11Worker",
    ] = field_(default="sync", metadata_cli=CliType.default("--worker-class {value}"))
    threads: int = field_(default=0, metadata_cli=CliType.default("--threads {value}"))
    worker_connections: int = field_(
        default=1000, metadata_cli=CliType.default("--worker-connections {value}")
    )
    max_requests: int = field_(
        default=0, metadata_cli=CliType.default("--max-requests {value}")
    )
    max_requests_jitter: int = field_(
        default=0, metadata_cli=CliType.default("--max-requests-jitter {value}")
    )
    timeout: int = field_(default=30, metadata_cli=CliType.default("--timeout {value}"))
    graceful_timeout: int = field_(
        default=30, metadata_cli=CliType.default("--graceful-timeout {value}")
    )
    keepalive: int = field_(
        default=2, metadata_cli=CliType.default("--keep-alive {value}")
    )
    limit_request_line: int = field_(
        default=4094, metadata_cli=CliType.default("--limit-request-line {value}")
    )
    limit_request_fields: int = field_(
        default=100, metadata_cli=CliType.default("--limit-request-fields {value}")
    )
    limit_request_field_size: int = field_(
        default=8190, metadata_cli=CliType.default("--limit-request-field_size {value}")
    )
    reload: bool = field_(default=False, metadata_cli=CliType.boolean("--reload"))
    reload_engine: Literal["auto", "poll", "inotify"] = field_(
        default="auto", metadata_cli=CliType.default("--reload-engine {value}")
    )
    reload_extra_files: list[str] = field_(
        default=None,
        default_factory=lambda: [],
        metadata_cli=CliType.default("--reload-extra-file {value}"),
    )
    spew: bool = field_(default=False, metadata_cli=CliType.boolean("--spew"))
    check_config: bool = field_(
        default=False, metadata_cli=CliType.boolean("--check-config")
    )
    print_config: bool = field_(
        default=False, metadata_cli=CliType.boolean("--print-config")
    )
    preload_app: bool = field_(default=False, metadata_cli=CliType.boolean("--preload"))
    sendfile: bool | None = field_(
        default=None, metadata_cli=CliType.boolean("--no-sendfile", bool_value=False)
    )
    reuse_port: bool = field_(
        default=False, metadata_cli=CliType.boolean("--reuse-port")
    )
    chdir: str = field_(default=".", metadata_cli=CliType.default("--chdir {value}"))
    daemon: bool = field_(default=False, metadata_cli=CliType.boolean("--daemon"))
    raw_env: list[str] = field_(
        default=None,
        default_factory=lambda: [],
        metadata_cli=CliType.multiple("--env {value}"),
    )
    pidfile: str | None = field_(
        default=None, metadata_cli=CliType.default("--pid {value}")
    )
    worker_tmp_dir: str | None = field_(
        default=None, metadata_cli=CliType.default("--worker-tmp-dir {value}")
    )
    user: int = field_(default=1000, metadata_cli=CliType.default("--user {value}"))
    group: int = field_(default=1000, metadata_cli=CliType.default("--group {value}"))
    umask: int = field_(default=0, metadata_cli=CliType.default("--umask {value}"))
    initgroups: bool = field_(
        default=False, metadata_cli=CliType.boolean("--initgroups")
    )
    tmp_upload_dir: str | None = field_(default=None, metadata_cli=None)
    secure_scheme_headers: dict[str, Any] = field_(
        default=None,
        default_factory=lambda: {
            "X-FORWARDED-PROTOCOL": "ssl",
            "X-FORWARDED-PROTO": "https",
            "X-FORWARDED-SSL": "on",
        },
        metadata_cli=None,
    )
    forwarded_allow_ips: str = field_(
        default="127.0.0.1,::1",
        metadata_cli=CliType.default("--forwarded-allow-ips {value}"),
    )
    accesslog: str | None = field_(
        default=None, metadata_cli=CliType.default("--access-logfile {value}")
    )
    disable_redirect_access_to_syslog: bool = field_(
        default=False,
        metadata_cli=CliType.boolean("--disable-redirect-access-to-syslog"),
    )
    access_log_format: str = field_(
        default='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"',
        metadata_cli=CliType.default("--access-logformat {value}"),
    )
    errorlog: str = field_(
        default="-", metadata_cli=CliType.default("--error-logfile {value}")
    )
    loglevel: Literal["debug", "info", "warning", "error", "critical"] = field_(
        default="info", metadata_cli=CliType.default("--log-level {value}")
    )
    capture_output: bool = field_(
        default=False, metadata_cli=CliType.boolean("--capture-output")
    )
    logger_class: str = field_(
        default="gunicorn.glogging.Logger",
        metadata_cli=CliType.default("--logger-class {value}"),
    )
    logconfig: str | None = field_(
        default=None, metadata_cli=CliType.default("--log-config {value}")
    )
    logconfig_dict: dict = field_(
        default=None, default_factory=lambda: {}, metadata_cli=None
    )
    logconfig_json: str | None = field_(
        default=None, metadata_cli=CliType.default("--log-config-json {value}")
    )
    syslog_addr: str = field_(
        default="udp://localhost:514",
        metadata_cli=CliType.default("--log-syslog-to {value}"),
    )
    syslog: bool = field_(default=False, metadata_cli=CliType.boolean("--log-syslog"))
    syslog_prefix: str | None = field_(
        default=None, metadata_cli=CliType.default("--log-syslog-prefix {value}")
    )
    syslog_facility: str = field_(
        default="user", metadata_cli=CliType.default("--log-syslog-facility {value}")
    )
    enable_stdio_inheritance: bool = field_(
        default=False, metadata_cli=CliType.boolean("--enable-stdio-inheritance")
    )
    statsd_host: str | None = field_(
        default=None, metadata_cli=CliType.default("--statsd-host {value}")
    )
    dogstatsd_tags: str = field_(
        default="", metadata_cli=CliType.default("--dogstatsd-tags {value}")
    )
    statsd_prefix: str = field_(
        default="", metadata_cli=CliType.default("--statsd-prefix {value}")
    )
    proc_name: str | None = field_(
        default=None, metadata_cli=CliType.default("--name {value}")
    )
    default_proc_name: str = field_(default="gunicorn", metadata_cli=None)
    pythonpath: str | None = field_(
        default=None, metadata_cli=CliType.default("--pythonpath {value}")
    )
    paste: str | None = field_(
        default=None, metadata_cli=CliType.default("--paster {value}")
    )
    on_starting: Callable = field_(default=lambda server: None, metadata_cli=None)
    on_reload: Callable = field_(default=lambda server: None, metadata_cli=None)
    when_ready: Callable = field_(default=lambda server: None, metadata_cli=None)
    pre_fork: Callable = field_(default=lambda server, worker: None, metadata_cli=None)
    post_fork: Callable = field_(default=lambda server, worker: None, metadata_cli=None)
    post_worker_init: Callable = field_(default=lambda worker: None, metadata_cli=None)
    worker_int: Callable = field_(default=lambda worker: None, metadata_cli=None)
    worker_abort: Callable = field_(default=lambda worker: None, metadata_cli=None)
    pre_exec: Callable = field_(default=lambda server: None, metadata_cli=None)
    pre_request: Callable = field_(
        default=lambda worker, req: worker.log.debug("%s %s", req.method, req.path),
        metadata_cli=None,
    )
    post_request: Callable = field_(
        default=lambda worker, req, environ, resp: None, metadata_cli=None
    )
    child_exit: Callable = field_(
        default=lambda server, worker: None, metadata_cli=None
    )
    worker_exit: Callable = field_(
        default=lambda server, worker: None, metadata_cli=None
    )
    nworkers_changed: Callable = field_(
        default=lambda server, new_value, old_value: None, metadata_cli=None
    )
    on_exit: Callable = field_(default=lambda server: None, metadata_cli=None)
    ssl_context: Callable[[Any, Any], Any] = field_(
        default=lambda config,
        default_ssl_context_factory: default_ssl_context_factory(),
        metadata_cli=None,
    )
    proxy_protocol: bool = field_(
        default=False, metadata_cli=CliType.boolean("--proxy-protocol")
    )
    proxy_allow_ips: str = field_(
        default="127.0.0.1,::1",
        metadata_cli=CliType.default("--proxy-allow-from {value}"),
    )
    keyfile: str | None = field_(
        default=None, metadata_cli=CliType.default("--keyfile {value}")
    )
    certfile: str | None = field_(
        default=None, metadata_cli=CliType.default("--certfile {value}")
    )
    ssl_version: int = field_(
        default=2, metadata_cli=CliType.default("--ssl-version {value}")
    )
    cert_reqs: int = field_(
        default=0, metadata_cli=CliType.default("--cert-reqs {value}")
    )
    ca_certs: str | None = field_(
        default=None, metadata_cli=CliType.default("--ca-certs {value}")
    )
    suppress_ragged_eofs: bool = field_(
        default=True, metadata_cli=CliType.boolean("--suppress-ragged-eofs")
    )
    do_handshake_on_connect: bool = field_(
        default=False, metadata_cli=CliType.boolean("--do-handshake-on-connect")
    )
    ciphers: str | None = field_(
        default=None, metadata_cli=CliType.default("--ciphers {value}")
    )
    raw_paste_global_conf: list[str] = field_(
        default=None,
        default_factory=lambda: [],
        metadata_cli=CliType.multiple("--paste-global {value}"),
    )
    permit_obsolete_folding: bool = field_(
        default=False, metadata_cli=CliType.boolean("--permit-obsolete-folding")
    )
    strip_header_spaces: bool = field_(
        default=False, metadata_cli=CliType.boolean("--strip-header-spaces")
    )
    permit_unconventional_http_method: bool = field_(
        default=False,
        metadata_cli=CliType.boolean("--permit-unconventional-http-method"),
    )
    permit_unconventional_http_version: bool = field_(
        default=False,
        metadata_cli=CliType.boolean("--permit-unconventional-http-version"),
    )
    casefold_http_method: bool = field_(
        default=False, metadata_cli=CliType.boolean("--casefold-http-method")
    )
    forwarder_headers: str = field_(
        default="SCRIPT_NAME,PATH_INFO",
        metadata_cli=CliType.default("--forwarder-headers {value}"),
    )
    header_map: Literal["drop", "refuse", "dangerous"] = field_(
        default="drop", metadata_cli=CliType.default("--header-map {value}")
    )

    def get_backend_bind(self) -> tuple[str, int]:
        """Return the backend host and port.

        Returns:
            tuple[str, int]: The host address and port.
        """
        host, port = self.bind[0].split(":")
        return host, int(port)

    def check_import(self):
        """Check package importation.

        Raises:
            ImportError: raise when some required packaging missing.
        """
        from importlib.util import find_spec

        errors: list[str] = []

        if IS_WINDOWS:
            errors.append(
                "The `GunicornBackendServer` only works on UNIX machines. We recommend using the `UvicornBackendServer` for Windows machines."
            )

        if find_spec("gunicorn") is None:
            errors.append(
                'The `gunicorn` package is required to run `GunicornBackendServer`. Run `pip install "gunicorn>=20.1.0"`.'
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
        self._app_uri = f"{self.get_app_module()}()"  # type: ignore
        self.loglevel = loglevel.value  # type: ignore
        self.bind = [f"{host}:{port}"]
        self._env = env  # type: ignore

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

    def run_prod(self) -> list[str]:
        """Run in production mode.

        Returns:
            list[str]: Command ready to be executed
        """
        self.check_import()
        command = ["gunicorn"]

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
        console.info(
            "For development mode, we recommand to use `UvicornBackendServer` than `GunicornBackendServer`"
        )

        from gunicorn.app.base import BaseApplication
        from gunicorn.util import import_app as gunicorn_import_app

        model = self.get_fields()
        options_ = {
            key: value
            for key, value in self.get_values().items()
            if value != model[key].default
        }

        class StandaloneApplication(BaseApplication):
            def __init__(self, app_uri, options=None):
                self.options = options or {}
                self._app_uri = app_uri
                super().__init__()

            def load_config(self):
                config = {
                    key: value
                    for key, value in self.options.items()
                    if key in self.cfg.settings and value is not None  # type: ignore
                }
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)  # type: ignore

            def load(self):
                return gunicorn_import_app(self._app_uri)

            def stop(self):
                from gunicorn.arbiter import Arbiter

                Arbiter(self).stop()

        self._app = StandaloneApplication(app_uri=self._app_uri, options=options_)  # type: ignore
        self._app.run()

    async def shutdown(self):
        """Shutdown the backend server."""
        if self._app and self._env == Env.DEV:
            self._app.stop()  # type: ignore
