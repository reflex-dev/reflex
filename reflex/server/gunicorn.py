"""The GunicornBackendServer."""

from __future__ import annotations

import os
import ssl
import sys
from typing import Any, Callable, Literal

from reflex.constants.base import Env, LogLevel
from reflex.server.base import CustomBackendServer
from reflex.utils import console

_mapping_attr_to_cli: dict[str, str] = {
    "config": "--config",
    "bind": "--bind",
    "backlog": "--backlog",
    "workers": "--workers",
    "worker_class": "--worker-class",
    "threads": "--threads",
    "worker_connections": "--worker-connections",
    "max_requests": "--max-requests",
    "max_requests_jitter": "--max-requests-jitter",
    "timeout": "--timeout",
    "graceful_timeout": "--graceful-timeout",
    "keepalive": "--keep-alive",
    "limit_request_line": "--limit-request-line",
    "limit_request_fields": "--limit-request-fields",
    "limit_request_field_size": "--limit-request-field_size",
    "reload": "--reload",
    "reload_engine": "--reload-engine",
    "reload_extra_files": "--reload-extra-file",
    "spew": "--spew",
    "check_config": "--check-config",
    "print_config": "--print-config",
    "preload_app": "--preload",
    "sendfile": "--no-sendfile",
    "reuse_port": "--reuse-port",
    "chdir": "--chdir",
    "daemon": "--daemon",
    "raw_env": "--env",
    "pidfile": "--pid",
    "worker_tmp_dir": "--worker-tmp-dir",
    "user": "--user",
    "group": "--group",
    "umask": "--umask",
    "initgroups": "--initgroups",
    "forwarded_allow_ips": "--forwarded-allow-ips",
    "accesslog": "--access-logfile",
    "disable_redirect_access_to_syslog": "--disable-redirect-access-to-syslog",
    "access_log_format": "--access-logformat",
    "errorlog": "--error-logfile",
    "loglevel": "--log-level",
    "capture_output": "--capture-output",
    "logger_class": "--logger-class",
    "logconfig": "--log-config",
    "logconfig_json": "--log-config-json",
    "syslog_addr": "--log-syslog-to",
    "syslog": "--log-syslog",
    "syslog_prefix": "--log-syslog-prefix",
    "syslog_facility": "--log-syslog-facility",
    "enable_stdio_inheritance": "--enable-stdio-inheritance",
    "statsd_host": "--statsd-host",
    "dogstatsd_tags": "--dogstatsd-tags",
    "statsd_prefix": "--statsd-prefix",
    "proc_name": "--name",
    "pythonpath": "--pythonpath",
    "paste": "--paster",
    "proxy_protocol": "--proxy-protocol",
    "proxy_allow_ips": "--proxy-allow-from",
    "keyfile": "--keyfile",
    "certfile": "--certfile",
    "ssl_version": "--ssl-version",
    "cert_reqs": "--cert-reqs",
    "ca_certs": "--ca-certs",
    "suppress_ragged_eofs": "--suppress-ragged-eofs",
    "do_handshake_on_connect": "--do-handshake-on-connect",
    "ciphers": "--ciphers",
    "raw_paste_global_conf": "--paste-global",
    "permit_obsolete_folding": "--permit-obsolete-folding",
    "strip_header_spaces": "--strip-header-spaces",
    "permit_unconventional_http_method": "--permit-unconventional-http-method",
    "permit_unconventional_http_version": "--permit-unconventional-http-version",
    "casefold_http_method": "--casefold-http-method",
    "forwarder_headers": "--forwarder-headers",
    "header_map": "--header-map",
}


class GunicornBackendServer(CustomBackendServer):
    """Gunicorn backendServer."""

    # https://github.com/benoitc/gunicorn/blob/bacbf8aa5152b94e44aa5d2a94aeaf0318a85248/gunicorn/config.py

    app_uri: str | None = None

    config: str = "./gunicorn.conf.py"
    """\
        :ref:`The Gunicorn config file<configuration_file>`.

        A string of the form ``PATH``, ``file:PATH``, or ``python:MODULE_NAME``.

        Only has an effect when specified on the command line or as part of an
        application specific configuration.

        By default, a file named ``gunicorn.conf.py`` will be read from the same
        directory where gunicorn is being run.
    """

    wsgi_app: str | None = None
    """\
        A WSGI application path in pattern ``$(MODULE_NAME):$(VARIABLE_NAME)``.
    """

    bind: list[str] = ["127.0.0.1:8000"]
    """\
        The socket to bind.

        A string of the form: ``HOST``, ``HOST:PORT``, ``unix:PATH``,
        ``fd://FD``. An IP is a valid ``HOST``.

        .. versionchanged:: 20.0
            Support for ``fd://FD`` got added.

        Multiple addresses can be bound. ex.::

            $ gunicorn -b 127.0.0.1:8000 -b [::1]:8000 test:app

        will bind the `test:app` application on localhost both on ipv6
        and ipv4 interfaces.

        If the ``PORT`` environment variable is defined, the default
        is ``['0.0.0.0:$PORT']``. If it is not defined, the default
        is ``['127.0.0.1:8000']``.
    """

    backlog: int = 2048
    """\
        The maximum number of pending connections.

        This refers to the number of clients that can be waiting to be served.
        Exceeding this number results in the client getting an error when
        attempting to connect. It should only affect servers under significant
        load.

        Must be a positive integer. Generally set in the 64-2048 range.
    """

    workers: int = 0
    """\
        The number of worker processes for handling requests.

        A positive integer generally in the ``2-4 x $(NUM_CORES)`` range.
        You'll want to vary this a bit to find the best for your particular
        application's work load.

        By default, the value of the ``WEB_CONCURRENCY`` environment variable,
        which is set by some Platform-as-a-Service providers such as Heroku. If
        it is not defined, the default is ``1``.
    """

    worker_class: Literal[
        "sync",
        "eventlet",
        "gevent",
        "tornado",
        "gthread",
        "uvicorn.workers.UvicornH11Worker",
    ] = "sync"
    """\
        The type of workers to use.

        The default class (``sync``) should handle most "normal" types of
        workloads. You'll want to read :doc:`design` for information on when
        you might want to choose one of the other worker classes. Required
        libraries may be installed using setuptools' ``extras_require`` feature.

        A string referring to one of the following bundled classes:

        * ``sync``
        * ``eventlet`` - Requires eventlet >= 0.24.1 (or install it via
            ``pip install gunicorn[eventlet]``)
        * ``gevent``   - Requires gevent >= 1.4 (or install it via
            ``pip install gunicorn[gevent]``)
        * ``tornado``  - Requires tornado >= 0.2 (or install it via
            ``pip install gunicorn[tornado]``)
        * ``gthread``  - Python 2 requires the futures package to be installed
            (or install it via ``pip install gunicorn[gthread]``)

        Optionally, you can provide your own worker by giving Gunicorn a
        Python path to a subclass of ``gunicorn.workers.base.Worker``.
        This alternative syntax will load the gevent class:
        ``gunicorn.workers.ggevent.GeventWorker``.
    """

    threads: int = 0
    """\
        The number of worker threads for handling requests.

        Run each worker with the specified number of threads.

        A positive integer generally in the ``2-4 x $(NUM_CORES)`` range.
        You'll want to vary this a bit to find the best for your particular
        application's work load.

        If it is not defined, the default is ``1``.

        This setting only affects the Gthread worker type.

        .. note::
        If you try to use the ``sync`` worker type and set the ``threads``
        setting to more than 1, the ``gthread`` worker type will be used
        instead.
    """

    worker_connections: int = 1000
    """\
        The maximum number of simultaneous clients.

        This setting only affects the ``gthread``, ``eventlet`` and ``gevent`` worker types.
    """

    max_requests: int = 0
    """\
        The maximum number of requests a worker will process before restarting.

        Any value greater than zero will limit the number of requests a worker
        will process before automatically restarting. This is a simple method
        to help limit the damage of memory leaks.

        If this is set to zero (the default) then the automatic worker
        restarts are disabled.
    """

    max_requests_jitter: int = 0
    """\
        The maximum jitter to add to the *max_requests* setting.

        The jitter causes the restart per worker to be randomized by
        ``randint(0, max_requests_jitter)``. This is intended to stagger worker
        restarts to avoid all workers restarting at the same time.
    """

    timeout: int = 30
    """\
        Workers silent for more than this many seconds are killed and restarted.

        Value is a positive number or 0. Setting it to 0 has the effect of
        infinite timeouts by disabling timeouts for all workers entirely.

        Generally, the default of thirty seconds should suffice. Only set this
        noticeably higher if you're sure of the repercussions for sync workers.
        For the non sync workers it just means that the worker process is still
        communicating and is not tied to the length of time required to handle a
        single request.
    """

    graceful_timeout: int = 30
    """\
        Timeout for graceful workers restart.

        After receiving a restart signal, workers have this much time to finish
        serving requests. Workers still alive after the timeout (starting from
        the receipt of the restart signal) are force killed.
    """

    keepalive: int = 2
    """\
        The number of seconds to wait for requests on a Keep-Alive connection.

        Generally set in the 1-5 seconds range for servers with direct connection
        to the client (e.g. when you don't have separate load balancer). When
        Gunicorn is deployed behind a load balancer, it often makes sense to
        set this to a higher value.

        .. note::
            ``sync`` worker does not support persistent connections and will
            ignore this option.
    """

    limit_request_line: int = 4094
    """\
        The maximum size of HTTP request line in bytes.

        This parameter is used to limit the allowed size of a client's
        HTTP request-line. Since the request-line consists of the HTTP
        method, URI, and protocol version, this directive places a
        restriction on the length of a request-URI allowed for a request
        on the server. A server needs this value to be large enough to
        hold any of its resource names, including any information that
        might be passed in the query part of a GET request. Value is a number
        from 0 (unlimited) to 8190.

        This parameter can be used to prevent any DDOS attack.
    """

    limit_request_fields: int = 100
    """\
        Limit the number of HTTP headers fields in a request.

        This parameter is used to limit the number of headers in a request to
        prevent DDOS attack. Used with the *limit_request_field_size* it allows
        more safety. By default this value is 100 and can't be larger than
        32768.
    """

    limit_request_field_size: int = 8190
    """\
        Limit the allowed size of an HTTP request header field.

        Value is a positive number or 0. Setting it to 0 will allow unlimited
        header field sizes.

        .. warning::
            Setting this parameter to a very high or unlimited value can open
            up for DDOS attacks.
    """

    reload: bool = False
    """\
        Restart workers when code changes.

        This setting is intended for development. It will cause workers to be
        restarted whenever application code changes.

        The reloader is incompatible with application preloading. When using a
        paste configuration be sure that the server block does not import any
        application code or the reload will not work as designed.

        The default behavior is to attempt inotify with a fallback to file
        system polling. Generally, inotify should be preferred if available
        because it consumes less system resources.

        .. note::
            In order to use the inotify reloader, you must have the ``inotify``
            package installed.
    """

    reload_engine: Literal["auto", "poll", "inotify"] = "auto"
    """\
        The implementation that should be used to power :ref:`reload`.

        Valid engines are:

        * ``'auto'``
        * ``'poll'``
        * ``'inotify'`` (requires inotify)
    """

    reload_extra_files: list[str] = []
    """\
        Extends :ref:`reload` option to also watch and reload on additional files
        (e.g., templates, configurations, specifications, etc.).
    """

    spew: bool = False
    """\
        Install a trace function that spews every line executed by the server.

        This is the nuclear option.
    """

    check_config: bool = False
    """\
        Check the configuration and exit. The exit status is 0 if the
        configuration is correct, and 1 if the configuration is incorrect.
    """

    print_config: bool = False
    """\
        Print the configuration settings as fully resolved. Implies :ref:`check-config`.
    """

    preload_app: bool = False
    """\
        Load application code before the worker processes are forked.

        By preloading an application you can save some RAM resources as well as
        speed up server boot times. Although, if you defer application loading
        to each worker process, you can reload your application code easily by
        restarting workers.
    """

    sendfile: bool | None = None
    """\
        Disables the use of ``sendfile()``.

        If not set, the value of the ``SENDFILE`` environment variable is used
        to enable or disable its usage.
    """

    reuse_port: bool = False
    """\
        Set the ``SO_REUSEPORT`` flag on the listening socket.
    """

    chdir: str = "."
    """\
        Change directory to specified directory before loading apps.
    """

    daemon: bool = False
    """\
        Daemonize the Gunicorn process.

        Detaches the server from the controlling terminal and enters the
        background.
    """

    raw_env: list[str] = []
    """\
        Set environment variables in the execution environment.

        Should be a list of strings in the ``key=value`` format.
    """

    pidfile: str | None = None
    """\
        A filename to use for the PID file.

        If not set, no PID file will be written.
    """

    worker_tmp_dir: str | None = None
    """\
        A directory to use for the worker heartbeat temporary file.

        If not set, the default temporary directory will be used.

        .. note::
            The current heartbeat system involves calling ``os.fchmod`` on
            temporary file handlers and may block a worker for arbitrary time
            if the directory is on a disk-backed filesystem.

            See :ref:`blocking-os-fchmod` for more detailed information
            and a solution for avoiding this problem.
    """

    user: int = os.geteuid()
    """\
        Switch worker processes to run as this user.

        A valid user id (as an integer) or the name of a user that can be
        retrieved with a call to ``pwd.getpwnam(value)`` or ``None`` to not
        change the worker process user.
    """

    group: int = os.getegid()
    """\
        Switch worker process to run as this group.

        A valid group id (as an integer) or the name of a user that can be
        retrieved with a call to ``pwd.getgrnam(value)`` or ``None`` to not
        change the worker processes group.
    """

    umask: int = 0
    """\
        A bit mask for the file mode on files written by Gunicorn.

        Note that this affects unix socket permissions.

        A valid value for the ``os.umask(mode)`` call or a string compatible
        with ``int(value, 0)`` (``0`` means Python guesses the base, so values
        like ``0``, ``0xFF``, ``0022`` are valid for decimal, hex, and octal
        representations)
    """

    initgroups: bool = False
    """\
        If true, set the worker process's group access list with all of the
        groups of which the specified username is a member, plus the specified
        group id.
    """

    tmp_upload_dir: str | None = None
    """\
        Directory to store temporary request data as they are read.

        This may disappear in the near future.

        This path should be writable by the process permissions set for Gunicorn
        workers. If not specified, Gunicorn will choose a system generated
        temporary directory.
    """

    secure_scheme_headers: dict[str, Any] = {
        "X-FORWARDED-PROTOCOL": "ssl",
        "X-FORWARDED-PROTO": "https",
        "X-FORWARDED-SSL": "on",
    }
    """\
        A dictionary containing headers and values that the front-end proxy
        uses to indicate HTTPS requests. If the source IP is permitted by
        :ref:`forwarded-allow-ips` (below), *and* at least one request header matches
        a key-value pair listed in this dictionary, then Gunicorn will set
        ``wsgi.url_scheme`` to ``https``, so your application can tell that the
        request is secure.

        If the other headers listed in this dictionary are not present in the request, they will be ignored,
        but if the other headers are present and do not match the provided values, then
        the request will fail to parse. See the note below for more detailed examples of this behaviour.

        The dictionary should map upper-case header names to exact string
        values. The value comparisons are case-sensitive, unlike the header
        names, so make sure they're exactly what your front-end proxy sends
        when handling HTTPS requests.

        It is important that your front-end proxy configuration ensures that
        the headers defined here can not be passed directly from the client.
    """

    forwarded_allow_ips: str = "127.0.0.1,::1"
    """\
        Front-end's IPs from which allowed to handle set secure headers.
        (comma separated).

        Set to ``*`` to disable checking of front-end IPs. This is useful for setups
        where you don't know in advance the IP address of front-end, but
        instead have ensured via other means that only your
        authorized front-ends can access Gunicorn.

        By default, the value of the ``FORWARDED_ALLOW_IPS`` environment
        variable. If it is not defined, the default is ``"127.0.0.1,::1"``.

        .. note::

            This option does not affect UNIX socket connections. Connections not associated with
            an IP address are treated as allowed, unconditionally.

        .. note::

            The interplay between the request headers, the value of ``forwarded_allow_ips``, and the value of
            ``secure_scheme_headers`` is complex. Various scenarios are documented below to further elaborate.
            In each case, we have a request from the remote address 134.213.44.18, and the default value of
            ``secure_scheme_headers``:

            .. code::

                secure_scheme_headers = {
                    'X-FORWARDED-PROTOCOL': 'ssl',
                    'X-FORWARDED-PROTO': 'https',
                    'X-FORWARDED-SSL': 'on'
                }


            .. list-table::
                :header-rows: 1
                :align: center
                :widths: auto

                * - ``forwarded-allow-ips``
                  - Secure Request Headers
                  - Result
                  - Explanation
                * - ``["127.0.0.1"]``
                  - ``X-Forwarded-Proto: https``
                  - ``wsgi.url_scheme = "http"``
                  - IP address was not allowed
                * - ``"*"``
                  - <none>
                  - ``wsgi.url_scheme = "http"``
                  - IP address allowed, but no secure headers provided
                * - ``"*"``
                  - ``X-Forwarded-Proto: https``
                  - ``wsgi.url_scheme = "https"``
                  - IP address allowed, one request header matched
                * - ``["134.213.44.18"]``
                  - ``X-Forwarded-Ssl: on`` ``X-Forwarded-Proto: http``
                  - ``InvalidSchemeHeaders()`` raised
                  - IP address allowed, but the two secure headers disagreed on if HTTPS was used
    """

    accesslog: str | None = None
    """\
        The Access log file to write to.

        ``'-'`` means log to stdout.
    """

    disable_redirect_access_to_syslog: bool = False
    """\
    Disable redirect access logs to syslog.
    """

    access_log_format: str = (
        '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    )
    """\
        The access log format.

        ===========  ===========
        Identifier   Description
        ===========  ===========
        h            remote address
        l            ``'-'``
        u            user name (if HTTP Basic auth used)
        t            date of the request
        r            status line (e.g. ``GET / HTTP/1.1``)
        m            request method
        U            URL path without query string
        q            query string
        H            protocol
        s            status
        B            response length
        b            response length or ``'-'`` (CLF format)
        f            referrer (note: header is ``referer``)
        a            user agent
        T            request time in seconds
        M            request time in milliseconds
        D            request time in microseconds
        L            request time in decimal seconds
        p            process ID
        {header}i    request header
        {header}o    response header
        {variable}e  environment variable
        ===========  ===========

        Use lowercase for header and environment variable names, and put
        ``{...}x`` names inside ``%(...)s``. For example::

            %({x-forwarded-for}i)s
    """

    errorlog: str = "-"
    """\
        The Error log file to write to.

        Using ``'-'`` for FILE makes gunicorn log to stderr.
    """

    loglevel: Literal["debug", "info", "warning", "error", "critical"] = "info"
    """\
        The granularity of Error log outputs.
    """

    capture_output: bool = False
    """\
        Redirect stdout/stderr to specified file in :ref:`errorlog`.
    """

    logger_class: str = "gunicorn.glogging.Logger"
    """\
        The logger you want to use to log events in Gunicorn.

        The default class (``gunicorn.glogging.Logger``) handles most
        normal usages in logging. It provides error and access logging.

        You can provide your own logger by giving Gunicorn a Python path to a
        class that quacks like ``gunicorn.glogging.Logger``.
    """

    logconfig: str | None = None
    """\
        The log config file to use.
        Gunicorn uses the standard Python logging module's Configuration
        file format.
    """

    logconfig_dict: dict = {}
    """\
        The log config dictionary to use, using the standard Python
        logging module's dictionary configuration format. This option
        takes precedence over the :ref:`logconfig` and :ref:`logconfig-json` options,
        which uses the older file configuration format and JSON
        respectively.

        Format: https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig

        For more context you can look at the default configuration dictionary for logging,
        which can be found at ``gunicorn.glogging.CONFIG_DEFAULTS``.
    """

    logconfig_json: str | None = None
    """\
        The log config to read config from a JSON file

        Format: https://docs.python.org/3/library/logging.config.html#logging.config.jsonConfig
    """

    syslog_addr: str = (
        "unix:///var/run/syslog"
        if sys.platform == "darwin"
        else (
            "unix:///var/run/log"
            if sys.platform
            in (
                "freebsd",
                "dragonfly",
            )
            else (
                "unix:///dev/log"
                if sys.platform == "openbsd"
                else "udp://localhost:514"
            )
        )
    )
    """\
        Address to send syslog messages.

        Address is a string of the form:
        * ``unix://PATH#TYPE`` : for unix domain socket, ``TYPE`` can be ``stream`` for the stream driver or ``dgram`` for the dgram driver, ``stream`` is the default
        * ``udp://HOST:PORT`` : for UDP sockets
        * ``tcp://HOST:PORT`` : for TCP sockets
    """

    syslog: bool = False
    """\
        Send *Gunicorn* logs to syslog.
    """

    syslog_prefix: str | None = None
    """\
        Makes Gunicorn use the parameter as program-name in the syslog entries.

        All entries will be prefixed by ``gunicorn.<prefix>``. By default the
        program name is the name of the process.
    """

    syslog_facility: str = "user"
    """\
        Syslog facility name
    """

    enable_stdio_inheritance: bool = False
    """\
        Enable stdio inheritance.

        Enable inheritance for stdio file descriptors in daemon mode.

        Note: To disable the Python stdout buffering, you can to set the user
        environment variable ``PYTHONUNBUFFERED`` .
    """

    statsd_host: str | None = None
    """\
        The address of the StatsD server to log to.

        Address is a string of the form:

        * ``unix://PATH`` : for a unix domain socket.
        * ``HOST:PORT`` : for a network address
    """

    dogstatsd_tags: str = ""
    """\
        A comma-delimited list of datadog statsd (dogstatsd) tags to append to
        statsd metrics.
    """

    statsd_prefix: str = ""
    """\
        Prefix to use when emitting statsd metrics (a trailing ``.`` is added,
        if not provided).
    """

    proc_name: str | None = None
    """\
        A base to use with setproctitle for process naming.

        This affects things like ``ps`` and ``top``. If you're going to be
        running more than one instance of Gunicorn you'll probably want to set a
        name to tell them apart. This requires that you install the setproctitle
        module.

        If not set, the *default_proc_name* setting will be used.
    """

    default_proc_name: str = "gunicorn"
    """\
        Internal setting that is adjusted for each type of application.
    """

    pythonpath: str | None = None
    """\
        A comma-separated list of directories to add to the Python path.

        e.g.
        ``'/home/djangoprojects/myproject,/home/python/mylibrary'``.
    """

    paste: str | None = None
    """\
        Load a PasteDeploy config file. The argument may contain a ``#``
        symbol followed by the name of an app section from the config file,
        e.g. ``production.ini#admin``.

        At this time, using alternate server blocks is not supported. Use the
        command line arguments to control server configuration instead.
    """

    on_starting: Callable = lambda server: None
    """\
        Called just before the master process is initialized.

        The callable needs to accept a single instance variable for the Arbiter.
    """

    on_reload: Callable = lambda server: None
    """\
    Called to recycle workers during a reload via SIGHUP.

    The callable needs to accept a single instance variable for the Arbiter.
    """

    when_ready: Callable = lambda server: None
    """\
        Called just after the server is started.

        The callable needs to accept a single instance variable for the Arbiter.
    """

    pre_fork: Callable = lambda server, worker: None
    """\
        Called just before a worker is forked.

        The callable needs to accept two instance variables for the Arbiter and
        new Worker.
    """

    post_fork: Callable = lambda server, worker: None
    """\
        Called just after a worker has been forked.

        The callable needs to accept two instance variables for the Arbiter and
        new Worker.
    """

    post_worker_init: Callable = lambda worker: None
    """\
        Called just after a worker has initialized the application.

        The callable needs to accept one instance variable for the initialized
        Worker.
    """

    worker_int: Callable = lambda worker: None
    """\
        Called just after a worker exited on SIGINT or SIGQUIT.

        The callable needs to accept one instance variable for the initialized
        Worker.
    """

    worker_abort: Callable = lambda worker: None
    """\
        Called when a worker received the SIGABRT signal.

        This call generally happens on timeout.

        The callable needs to accept one instance variable for the initialized
        Worker.
    """

    pre_exec: Callable = lambda server: None
    """\
        Called just before a new master process is forked.

        The callable needs to accept a single instance variable for the Arbiter.
    """

    pre_request: Callable = lambda worker, req: worker.log.debug(
        "%s %s", req.method, req.path
    )
    """\
        Called just before a worker processes the request.

        The callable needs to accept two instance variables for the Worker and
        the Request.
    """

    post_request: Callable = lambda worker, req, environ, resp: None
    """\
        Called after a worker processes the request.

        The callable needs to accept two instance variables for the Worker and
        the Request.
    """

    child_exit: Callable = lambda server, worker: None
    """\
        Called just after a worker has been exited, in the master process.

        The callable needs to accept two instance variables for the Arbiter and
        the just-exited Worker.
    """

    worker_exit: Callable = lambda server, worker: None
    """\
        Called just after a worker has been exited, in the worker process.

        The callable needs to accept two instance variables for the Arbiter and
        the just-exited Worker.
    """

    nworkers_changed: Callable = lambda server, new_value, old_value: None
    """\
        Called just after *num_workers* has been changed.

        The callable needs to accept an instance variable of the Arbiter and
        two integers of number of workers after and before change.

        If the number of workers is set for the first time, *old_value* would
        be ``None``.
    """

    on_exit: Callable = lambda server: None
    """\
        Called just before exiting Gunicorn.

        The callable needs to accept a single instance variable for the Arbiter.
    """

    ssl_context: Callable = (
        lambda config, default_ssl_context_factory: default_ssl_context_factory()
    )
    """\
        Called when SSLContext is needed.

        Allows customizing SSL context.

        The callable needs to accept an instance variable for the Config and
        a factory function that returns default SSLContext which is initialized
        with certificates, private key, cert_reqs, and ciphers according to
        config and can be further customized by the callable.
        The callable needs to return SSLContext object.

        Following example shows a configuration file that sets the minimum TLS version to 1.3:

        .. code-block:: python

            def ssl_context(conf, default_ssl_context_factory):
                import ssl
                context = default_ssl_context_factory()
                context.minimum_version = ssl.TLSVersion.TLSv1_3
                return context
    """

    proxy_protocol: bool = False
    """\
        Enable detect PROXY protocol (PROXY mode).

        Allow using HTTP and Proxy together. It may be useful for work with
        stunnel as HTTPS frontend and Gunicorn as HTTP server.

        PROXY protocol: http://haproxy.1wt.eu/download/1.5/doc/proxy-protocol.txt

        Example for stunnel config::

            [https]
            protocol = proxy
            accept  = 443
            connect = 80
            cert = /etc/ssl/certs/stunnel.pem
            key = /etc/ssl/certs/stunnel.key
    """

    proxy_allow_ips: str = "127.0.0.1,::1"
    """\
        Front-end's IPs from which allowed accept proxy requests (comma separated).

        Set to ``*`` to disable checking of front-end IPs. This is useful for setups
        where you don't know in advance the IP address of front-end, but
        instead have ensured via other means that only your
        authorized front-ends can access Gunicorn.

        .. note::

            This option does not affect UNIX socket connections. Connections not associated with
            an IP address are treated as allowed, unconditionally.
    """

    keyfile: str | None = None
    """\
        SSL key file
    """

    certfile: str | None = None
    """\
        SSL certificate file
    """

    ssl_version: int = (
        ssl.PROTOCOL_TLS if hasattr(ssl, "PROTOCOL_TLS") else ssl.PROTOCOL_SSLv23
    )
    """\
        SSL version to use (see stdlib ssl module's).

        .. deprecated:: 21.0
        The option is deprecated and it is currently ignored. Use :ref:`ssl-context` instead.

        ============= ============
        --ssl-version Description
        ============= ============
        SSLv3         SSLv3 is not-secure and is strongly discouraged.
        SSLv23        Alias for TLS. Deprecated in Python 3.6, use TLS.
        TLS           Negotiate highest possible version between client/server.
                    Can yield SSL. (Python 3.6+)
        TLSv1         TLS 1.0
        TLSv1_1       TLS 1.1 (Python 3.4+)
        TLSv1_2       TLS 1.2 (Python 3.4+)
        TLS_SERVER    Auto-negotiate the highest protocol version like TLS,
                    but only support server-side SSLSocket connections.
                    (Python 3.6+)
        ============= ============

        .. versionchanged:: 19.7
        The default value has been changed from ``ssl.PROTOCOL_TLSv1`` to
        ``ssl.PROTOCOL_SSLv23``.
        .. versionchanged:: 20.0
        This setting now accepts string names based on ``ssl.PROTOCOL_``
        constants.
        .. versionchanged:: 20.0.1
        The default value has been changed from ``ssl.PROTOCOL_SSLv23`` to
        ``ssl.PROTOCOL_TLS`` when Python >= 3.6 .
    """

    cert_reqs: int = ssl.CERT_NONE
    """\
        Whether client certificate is required (see stdlib ssl module's)

        ===========  ===========================
        --cert-reqs      Description
        ===========  ===========================
        `0`          ``ssl.CERT_NONE``
        `1`          ``ssl.CERT_OPTIONAL``
        `2`          ``ssl.CERT_REQUIRED``
        ===========  ===========================
    """

    ca_certs: str | None = None
    """\
        CA certificates file
    """

    suppress_ragged_eofs: bool = True
    """\
        Suppress ragged EOFs (see stdlib ssl module's)
    """

    do_handshake_on_connect: bool = False
    """\
        Whether to perform SSL handshake on socket connect (see stdlib ssl module's)
    """

    ciphers: str | None = None
    """\
        SSL Cipher suite to use, in the format of an OpenSSL cipher list.

        By default we use the default cipher list from Python's ``ssl`` module,
        which contains ciphers considered strong at the time of each Python
        release.

        As a recommended alternative, the Open Web App Security Project (OWASP)
        offers `a vetted set of strong cipher strings rated A+ to C-
        <https://www.owasp.org/index.php/TLS_Cipher_String_Cheat_Sheet>`_.
        OWASP provides details on user-agent compatibility at each security level.

        See the `OpenSSL Cipher List Format Documentation
        <https://www.openssl.org/docs/manmaster/man1/ciphers.html#CIPHER-LIST-FORMAT>`_
        for details on the format of an OpenSSL cipher list.
    """

    raw_paste_global_conf: list[str] = []
    """\
        Set a PasteDeploy global config variable in ``key=value`` form.

        The option can be specified multiple times.

        The variables are passed to the PasteDeploy entrypoint. Example::

            $ gunicorn -b 127.0.0.1:8000 --paste development.ini --paste-global FOO=1 --paste-global BAR=2
    """

    permit_obsolete_folding: bool = False
    """\
        Permit requests employing obsolete HTTP line folding mechanism

        The folding mechanism was deprecated by rfc7230 Section 3.2.4 and will not be
        employed in HTTP request headers from standards-compliant HTTP clients.

        This option is provided to diagnose backwards-incompatible changes.
        Use with care and only if necessary. Temporary; the precise effect of this option may
        change in a future version, or it may be removed altogether.
    """

    strip_header_spaces: bool = False
    """\
        Strip spaces present between the header name and the the ``:``.

        This is known to induce vulnerabilities and is not compliant with the HTTP/1.1 standard.
        See https://portswigger.net/research/http-desync-attacks-request-smuggling-reborn.

        Use with care and only if necessary. Deprecated; scheduled for removal in 25.0.0
    """

    permit_unconventional_http_method: bool = False
    """\
        Permit HTTP methods not matching conventions, such as IANA registration guidelines

        This permits request methods of length less than 3 or more than 20,
        methods with lowercase characters or methods containing the # character.
        HTTP methods are case sensitive by definition, and merely uppercase by convention.

        If unset, Gunicorn will apply nonstandard restrictions and cause 400 response status
        in cases where otherwise 501 status is expected. While this option does modify that
        behaviour, it should not be depended upon to guarantee standards-compliant behaviour.
        Rather, it is provided temporarily, to assist in diagnosing backwards-incompatible
        changes around the incomplete application of those restrictions.

        Use with care and only if necessary. Temporary; scheduled for removal in 24.0.0
    """

    permit_unconventional_http_version: bool = False
    """\
        Permit HTTP version not matching conventions of 2023

        This disables the refusal of likely malformed request lines.
        It is unusual to specify HTTP 1 versions other than 1.0 and 1.1.

        This option is provided to diagnose backwards-incompatible changes.
        Use with care and only if necessary. Temporary; the precise effect of this option may
        change in a future version, or it may be removed altogether.
    """

    casefold_http_method: bool = False
    """\
        Transform received HTTP methods to uppercase

        HTTP methods are case sensitive by definition, and merely uppercase by convention.

        This option is provided because previous versions of gunicorn defaulted to this behaviour.

        Use with care and only if necessary. Deprecated; scheduled for removal in 24.0.0
    """

    forwarder_headers: str = "SCRIPT_NAME,PATH_INFO"
    """\
        A list containing upper-case header field names that the front-end proxy
        (see :ref:`forwarded-allow-ips`) sets, to be used in WSGI environment.

        This option has no effect for headers not present in the request.

        This option can be used to transfer ``SCRIPT_NAME``, ``PATH_INFO``
        and ``REMOTE_USER``.

        It is important that your front-end proxy configuration ensures that
        the headers defined here can not be passed directly from the client.
    """

    header_map: Literal["drop", "refuse", "dangerous"] = "drop"
    """\
        Configure how header field names are mapped into environ

        Headers containing underscores are permitted by RFC9110,
        but gunicorn joining headers of different names into
        the same environment variable will dangerously confuse applications as to which is which.

        The safe default ``drop`` is to silently drop headers that cannot be unambiguously mapped.
        The value ``refuse`` will return an error if a request contains *any* such header.
        The value ``dangerous`` matches the previous, not advisable, behaviour of mapping different
        header field names into the same environ name.

        If the source is permitted as explained in :ref:`forwarded-allow-ips`, *and* the header name is
        present in :ref:`forwarder-headers`, the header is mapped into environment regardless of
        the state of this setting.

        Use with care and only if necessary and after considering if your problem could
        instead be solved by specifically renaming or rewriting only the intended headers
        on a proxy in front of Gunicorn.
    """

    def check_import(self, extra: bool = False):
        """Check package importation."""
        from importlib.util import find_spec

        errors: list[str] = []

        if find_spec("gunicorn") is None:
            errors.append(
                'The `gunicorn` package is required to run `GunicornBackendServer`. Run `pip install "gunicorn>=20.1.0"`.'
            )

        if errors:
            console.error("\n".join(errors))
            sys.exit()

    def setup(self, host: str, port: int, loglevel: LogLevel, env: Env):
        """Setup."""
        self.app_uri = f"{self.get_app_module()}()"
        self.loglevel = loglevel.value  # type: ignore
        self.bind = [f"{host}:{port}"]

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
            self.preload_app = True

        if env == Env.DEV:
            self.reload = True

    def run_prod(self) -> list[str]:
        """Run in production mode."""
        self.check_import()

        command = ["gunicorn"]

        for key, field in self.get_fields().items():
            if key != "app":
                value = getattr(self, key)
                if _mapping_attr_to_cli.get(key) and value != field.default:
                    if isinstance(value, list):
                        for v in value:
                            command += [_mapping_attr_to_cli[key], str(v)]
                    elif isinstance(value, bool):
                        if (key == "sendfile" and value is False) or (
                            key != "sendfile" and value
                        ):
                            command.append(_mapping_attr_to_cli[key])
                    else:
                        command += [_mapping_attr_to_cli[key], str(value)]

        return command + [f"{self.get_app_module()}()"]

    def run_dev(self):
        """Run in development mode."""
        self.check_import()
        console.info(
            "For development mode, we recommand to use `UvicornBackendServer` than `GunicornBackendServer`"
        )

        from gunicorn.app.base import BaseApplication
        from gunicorn.util import import_app as gunicorn_import_app

        options_ = self.dict()
        options_.pop("app", None)

        class StandaloneApplication(BaseApplication):
            def __init__(self, app_uri, options=None):
                self.options = options or {}
                self.app_uri = app_uri
                super().__init__()

            def load_config(self):
                config = {
                    key: value
                    for key, value in self.options.items()
                    if key in self.cfg.settings and value is not None
                }  # type: ignore
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)  # type: ignore

            def load(self):
                return gunicorn_import_app(self.app_uri)

        StandaloneApplication(app_uri=self.app_uri, options=options_).run()
