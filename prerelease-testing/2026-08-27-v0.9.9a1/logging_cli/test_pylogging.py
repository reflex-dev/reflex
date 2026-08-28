"""Pure-python checks of the reflex 0.9.9a1 logging pipeline (no server).

Run with the isolated PyPI-installed venv python:
    $SB/envs/smoke/bin/python test_pylogging.py

Each check prints PASS/FAIL lines; exits nonzero if any FAIL.
Covers: LogLevel ordering/to_logging_level, import-reflex bootstrap behavior,
library-mode handler policy (no handler attached, propagation preserved),
user logging config not clobbered, double-import safety, console.* deprecation
shims, reflex.utils.log re-export.
"""

import io
import logging
import sys
import warnings

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = ""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    # --- capture pre-import state of root logger ---
    logging.basicConfig(
        level=logging.INFO, format="USERFMT %(levelname)s %(name)s %(message)s"
    )
    root = logging.getLogger()
    pre_handlers = list(root.handlers)
    pre_level = root.level

    with warnings.catch_warnings(record=True) as import_warnings:
        warnings.simplefilter("always")
        import reflex  # noqa: F401
    check(
        "import reflex emits no warnings",
        len(import_warnings) == 0,
        f"warnings={[str(w.message)[:100] for w in import_warnings]}",
    )

    # --- bootstrap timing: PR #6863 says "import reflex bootstraps the
    # reflex-owned loggers", but reflex lazy-loads; the pipeline actually
    # loads on first framework use (e.g. rx.App()). Recorded as ANOMALY info.
    pipeline_loaded_on_import = "reflex_base.utils.log" in sys.modules
    check(
        "ANOMALY-CHECK: bare 'import reflex' loads logging pipeline "
        "(PR #6863 claim; currently lazy — loads on first framework use)",
        pipeline_loaded_on_import,
        f"loaded={pipeline_loaded_on_import}",
    )
    reflex.App()  # first framework use triggers the pipeline bootstrap
    check(
        "logging pipeline loaded after rx.App()",
        "reflex_base.utils.log" in sys.modules,
    )

    # --- bootstrap: package loggers parented under 'reflex' ---
    rx_logger = logging.getLogger("reflex")
    for name in ("reflex_base", "reflex_cli", "reflex_components_core"):
        check(
            f"logger {name!r} parented under 'reflex'",
            logging.getLogger(name).parent is rx_logger,
            f"parent={logging.getLogger(name).parent}",
        )

    # --- library mode: no handlers attached by reflex ---
    check(
        "'reflex' logger has no handlers outside CLI (library mode)",
        rx_logger.handlers == [],
        f"handlers={rx_logger.handlers}",
    )
    check(
        "'reflex_base' logger has no handlers outside CLI",
        logging.getLogger("reflex_base").handlers == [],
        f"handlers={logging.getLogger('reflex_base').handlers}",
    )
    check(
        "'reflex' logger still propagates to root (library mode)",
        rx_logger.propagate is True,
    )

    # --- user's own logging config not clobbered ---
    check(
        "root logger handlers unchanged after import reflex",
        list(root.handlers) == pre_handlers,
        f"pre={pre_handlers} post={root.handlers}",
    )
    check(
        "root logger level unchanged after import reflex",
        root.level == pre_level,
        f"pre={pre_level} post={root.level}",
    )

    # --- LogLevel enum ordering + to_logging_level ---
    from reflex.constants import LogLevel

    order = [
        LogLevel.DEBUG,
        LogLevel.DEFAULT,
        LogLevel.INFO,
        LogLevel.WARNING,
        LogLevel.ERROR,
        LogLevel.CRITICAL,
    ]
    ordering_ok = all(order[i] < order[i + 1] for i in range(len(order) - 1))
    check("LogLevel strict ordering debug<default<info<warning<error<critical", ordering_ok)
    check(
        "LogLevel critical NOT <= debug (banner-bug fix)",
        not (LogLevel.CRITICAL <= LogLevel.DEBUG),
    )
    check("LogLevel debug <= debug", LogLevel.DEBUG <= LogLevel.DEBUG)
    check(
        "LogLevel warning > info and info >= info",
        LogLevel.WARNING > LogLevel.INFO and LogLevel.INFO >= LogLevel.INFO,
    )
    expected_levels = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.DEFAULT: logging.INFO,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL,
    }
    for lvl, expected in expected_levels.items():
        got = lvl.to_logging_level()
        check(
            f"LogLevel.{lvl.name}.to_logging_level() == {expected}",
            got == expected,
            f"got={got}",
        )
    check(
        "LogLevel.from_string round-trips",
        LogLevel.from_string("critical") is LogLevel.CRITICAL
        and LogLevel.from_string(None) is None
        and LogLevel.from_string("bogus") is None,
    )

    # --- reflex.utils.log re-export of reflex_base.utils.log ---
    import reflex.utils.log as rx_log
    import reflex_base.utils.log as base_log

    reexports = all(
        getattr(rx_log, n, None) is getattr(base_log, n, None)
        for n in ("set_log_level", "deprecate", "timing", "is_json_mode")
    )
    check(
        "reflex.utils.log re-exports reflex_base.utils.log API",
        reexports,
        f"module={rx_log}",
    )

    # --- double import / repeated bootstrap is idempotent ---
    base_log.bootstrap()
    base_log.bootstrap()
    check(
        "repeated bootstrap() adds no handlers",
        rx_logger.handlers == [] and logging.getLogger("reflex_base").handlers == [],
    )
    check(
        "repeated bootstrap keeps parenting",
        logging.getLogger("reflex_base").parent is rx_logger,
    )

    # --- framework logger records propagate to the app's root handler ---
    stream = io.StringIO()
    capture = logging.StreamHandler(stream)
    capture.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    capture.setLevel(logging.DEBUG)
    root.addHandler(capture)
    try:
        logging.getLogger("reflex_base.some.module").warning("framework-warn-rec")
        logging.getLogger("reflex_cli.x").warning("cli-warn-rec")
    finally:
        root.removeHandler(capture)
    out = stream.getvalue()
    check(
        "reflex_base logger records propagate to app root handler",
        "framework-warn-rec" in out and "reflex_base.some.module" in out,
        f"out={out!r}",
    )
    check(
        "reflex_cli logger records propagate to app root handler",
        "cli-warn-rec" in out,
    )

    # --- console deprecation shims: legacy print behavior + deprecation banner ---
    # (Per PR #6867 the shims keep their legacy rich-print behavior; they do
    # NOT route through logging. Verified in a subprocess capturing real
    # stdout/stderr, because rich writes to the underlying streams.)
    import subprocess

    child = (
        "import warnings, sys\n"
        "warnings.simplefilter('always')\n"
        "from reflex.utils import console\n"
        "from reflex.constants import LogLevel\n"
        "console.info('hello-info-msg')\n"
        "console.warn('hello-warn-msg')\n"
        "console.error('hello-error-msg')\n"
        "console.debug('hidden-debug-at-info')\n"
        "console.success('hello-success-msg')\n"
        "console.log('hello-log-msg')\n"
        "with console.timing('hello-timing'):\n"
        "    pass\n"
        "console.set_log_level(LogLevel.DEBUG)\n"
        "console.debug('visible-debug-at-debug')\n"
        "with console.timing('timing-at-debug'):\n"
        "    pass\n"
        "console.set_log_level(LogLevel.WARNING)\n"
        "console.info('hidden-info-at-warning')\n"
        "console.warn('visible-warn-at-warning')\n"
        "console.info('hidden-info-at-warning-2')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", child],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "REFLEX_TELEMETRY_ENABLED": "false"},
    )
    both = proc.stdout + proc.stderr
    print("---- shim child stdout ----")
    print(proc.stdout)
    print("---- shim child stderr ----")
    print(proc.stderr)
    print("---------------------------")
    check("shim child exited 0", proc.returncode == 0, f"rc={proc.returncode}")
    for expected in (
        "Info: hello-info-msg",
        "Warning: hello-warn-msg",
        "Success: hello-success-msg",
        "hello-log-msg",
    ):
        check(f"console shim still prints {expected!r}", expected in proc.stdout)
    check("console.error prints to stderr", "hello-error-msg" in proc.stderr)
    check(
        "console.debug hidden at INFO level",
        "hidden-debug-at-info" not in both,
    )
    check(
        "console.debug visible at DEBUG level",
        "visible-debug-at-debug" in both,
    )
    check(
        "console.timing prints duration at debug level",
        "timing-at-debug" in both,
    )
    check(
        "console.info hidden at WARNING level",
        "hidden-info-at-warning" not in both and "hidden-info-at-warning-2" not in both,
    )
    check(
        "console.warn visible at WARNING level",
        "visible-warn-at-warning" in both,
    )
    dep_count = both.count("has been deprecated")
    check(
        "each shim helper emits a DeprecationWarning banner",
        dep_count >= 7,
        f"count={dep_count}",
    )
    check("deprecation mentions removal in 1.0", "removed in 1.0" in both)
    check(
        "deprecation points at user call site (<string>:N)",
        "(<string>:" in both.replace("\n", ""),
        "location tag not found (informational)",
    )

    # --- set_log_level type validation + library-mode semantics ---
    try:
        base_log.set_log_level("info")  # type: ignore[arg-type]
        check("set_log_level rejects plain string", False, "no TypeError raised")
    except TypeError:
        check("set_log_level rejects plain string", True)
    base_log.set_log_level(LogLevel.WARNING)
    check(
        "library-mode set_log_level adjusts 'reflex' logger level",
        rx_logger.level == logging.WARNING,
        f"level={rx_logger.level}",
    )
    check(
        "library-mode set_log_level attaches no handlers",
        rx_logger.handlers == [],
    )
    check("get_log_level reflects set", base_log.get_log_level() is LogLevel.WARNING)
    base_log.set_log_level(LogLevel.INFO)

    fails = [r for r in RESULTS if not r[1]]
    print(f"\nSUMMARY: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
