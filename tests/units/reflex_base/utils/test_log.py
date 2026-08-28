"""Tests for the standard logging pipeline in reflex_base.utils.log."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from reflex_base.constants import LogLevel
from reflex_base.utils import console, log
from rich.console import Console

logger = logging.getLogger("reflex_base.tests.logs")


@pytest.fixture(autouse=True)
def clean_pipeline(monkeypatch):
    """Configure the managed pipeline at INFO with empty dedupe state.

    Restores library mode (no sinks, propagation on) after each test so the
    rest of the unit suite keeps standard root-logger capture.

    Yields:
        None.
    """
    monkeypatch.delenv("REFLEX_LOG_JSON", raising=False)
    monkeypatch.delenv("REFLEX_LOGLEVEL", raising=False)
    monkeypatch.setenv(log._MANAGED_ENV_VAR, "true")
    monkeypatch.setattr(log, "_log_level", LogLevel.INFO)
    log._dedupe_filter().seen.clear()
    log.configure()
    yield
    log._dedupe_filter().seen.clear()
    log._reset()


@pytest.fixture
def library_mode(monkeypatch):
    """Drop into library mode: no managed marker, no sinks attached."""
    monkeypatch.delenv(log._MANAGED_ENV_VAR, raising=False)
    log._reset()


def test_rich_output_parity(capsys):
    """Each level renders with the legacy prefix and stream."""
    log.set_log_level(LogLevel.DEBUG)
    logger.debug("d")
    logger.info("i")
    logger.log(log.SUCCESS, "s")
    logger.warning("w")
    logger.error("e")
    out, err = capsys.readouterr()
    assert out == "Debug: d\nInfo: i\nSuccess: s\nWarning: w\n"
    assert err == "e\n"


def test_markup_rendered_when_opted_in(capsys):
    """Records carrying ``rich=True`` render their markup."""
    logger.info("hello [bold]world[/bold]", extra={"rich": True})
    out, _ = capsys.readouterr()
    assert out == "Info: hello world\n"


def test_markup_literal_by_default(capsys):
    """Without the opt-in, bracketed text renders literally."""
    logger.info("AssertionErr: foo[bar] != 'baz'")
    out, _ = capsys.readouterr()
    assert out == "Info: AssertionErr: foo[bar] != 'baz'\n"


def test_warning_with_markup_tags_stays_literal(capsys):
    """User data resembling rich markup is neither styled nor escaped.

    Messages must not be markup-escaped at the call site: the sink renders
    them raw, so the escape backslashes would print literally, while markup
    injection stays impossible because markup is off by default.
    """
    logger.warning("got [red]x[/red] of type dict[str, str]")
    out, _ = capsys.readouterr()
    assert out == "Warning: got [red]x[/red] of type dict[str, str]\n"


def test_level_gating(capsys):
    """Records below the configured level are dropped."""
    log.set_log_level(LogLevel.WARNING)
    logger.info("hidden")
    logger.warning("shown")
    out, _ = capsys.readouterr()
    assert out == "Warning: shown\n"


def test_default_level_gates_like_info(capsys):
    """The DEFAULT log level shows info but not debug records."""
    log.set_log_level(LogLevel.DEFAULT)
    logger.debug("hidden")
    logger.info("shown")
    out, _ = capsys.readouterr()
    assert out == "Info: shown\n"


def test_dedupe(capsys):
    """Records with dedupe set are only emitted once."""
    logger.info("once", extra={"dedupe": True})
    logger.info("once", extra={"dedupe": True})
    logger.info("twice")
    logger.info("twice")
    out, _ = capsys.readouterr()
    assert out == "Info: once\nInfo: twice\nInfo: twice\n"


def test_dedupe_filter_stores_hashes_not_messages():
    """The seen-set retains hashes only, never the deduped messages."""
    logger.info("sensitive message contents", extra={"dedupe": True})
    seen = log._dedupe_filter().seen
    assert seen
    assert all(isinstance(entry, int) for entry in seen)


def test_json_mode(monkeypatch, capsys):
    """JSON mode emits one parseable record per line."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    logger.info("hello [bold]world[/bold]", extra={"rich": True})
    logger.error("boom")
    out, err = capsys.readouterr()
    record = json.loads(out)
    assert record["level"] == "info"
    assert record["message"] == "hello world"
    assert record["logger"] == logger.name
    assert "timestamp" in record
    assert "location" in record
    assert "pid" in record
    error_record = json.loads(err)
    assert error_record["level"] == "error"
    assert error_record["message"] == "boom"


def test_json_mode_preserves_brackets_in_plain_records(monkeypatch, capsys):
    """Only ``rich=True`` records are markup-stripped in JSON output."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    logger.info("foo[bar]")
    out, _ = capsys.readouterr()
    assert json.loads(out)["message"] == "foo[bar]"


def test_json_mode_success_level(monkeypatch, capsys):
    """The custom SUCCESS level serializes with its own name."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    logger.log(log.SUCCESS, "done")
    out, _ = capsys.readouterr()
    assert json.loads(out)["level"] == "success"


def test_configure_idempotent():
    """Repeated configure calls never stack handlers."""
    log.configure()
    log.configure()
    reflex_logger = logging.getLogger("reflex")
    assert reflex_logger.handlers.count(log._console_handler()) == 1
    assert log._json_handler() not in reflex_logger.handlers
    assert all(
        not logging.getLogger(name).handlers for name in log.PACKAGE_LOGGER_NAMES
    )


def test_configure_swaps_handler_in_json_mode(monkeypatch):
    """Switching JSON mode swaps the sink instead of stacking it."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    reflex_logger = logging.getLogger("reflex")
    assert log._json_handler() in reflex_logger.handlers
    assert log._console_handler() not in reflex_logger.handlers


def test_configure_cuts_propagation_to_root():
    """Managed mode owns the terminal: records never reach root handlers."""
    root_sink = mock.Mock(spec=logging.Handler)
    root_sink.level = logging.DEBUG
    logging.getLogger().addHandler(root_sink)
    try:
        assert logging.getLogger("reflex").propagate is False
        logger.warning("managed")
        root_sink.handle.assert_not_called()
    finally:
        logging.getLogger().removeHandler(root_sink)


def test_configure_removes_file_handler_when_full_logging_is_disabled(monkeypatch):
    """Disabling full logging detaches its handler again."""
    handler = logging.NullHandler()
    monkeypatch.setattr(log, "_file_handler", lambda: handler)
    monkeypatch.setenv("REFLEX_ENABLE_FULL_LOGGING", "true")
    try:
        log.configure()
        assert handler in logging.getLogger("reflex").handlers

        monkeypatch.setenv("REFLEX_ENABLE_FULL_LOGGING", "false")
        log.configure()
        assert handler not in logging.getLogger("reflex").handlers
    finally:
        logging.getLogger("reflex").removeHandler(handler)


def test_set_log_level_env_propagation(monkeypatch):
    """Changing the level exports REFLEX_LOGLEVEL for subprocesses."""
    import os

    monkeypatch.delenv("REFLEX_LOGLEVEL", raising=False)
    log.set_log_level(LogLevel.DEBUG)
    assert os.environ.get("REFLEX_LOGLEVEL") == "debug"
    assert log.get_log_level() is LogLevel.DEBUG
    assert log.is_debug()


def test_set_log_level_rejects_strings():
    """Passing a raw string raises a TypeError."""
    with pytest.raises(TypeError):
        log.set_log_level("debug")  # pyright: ignore[reportArgumentType]


def test_set_log_level_none_is_noop():
    """Passing None keeps the current level."""
    log.set_log_level(None)
    assert log.get_log_level() is LogLevel.INFO


def test_set_log_level_in_library_mode_attaches_nothing(library_mode):
    """Library-mode level tuning adjusts the logger but never adds sinks."""
    log.set_log_level(LogLevel.DEBUG)
    reflex_logger = logging.getLogger("reflex")
    assert reflex_logger.level == logging.DEBUG
    assert reflex_logger.handlers == []
    assert reflex_logger.propagate is True


def test_loglevel_total_ordering():
    """All comparison operators use enum position, not string order."""
    assert LogLevel.CRITICAL > LogLevel.DEBUG
    assert LogLevel.DEBUG < LogLevel.DEFAULT < LogLevel.INFO
    assert LogLevel.ERROR >= LogLevel.WARNING
    assert LogLevel.DEBUG <= LogLevel.DEBUG
    assert not LogLevel.CRITICAL < LogLevel.ERROR


def test_loglevel_to_logging_level():
    """LogLevel maps onto stdlib numeric levels."""
    assert LogLevel.DEBUG.to_logging_level() == logging.DEBUG
    assert LogLevel.DEFAULT.to_logging_level() == logging.INFO
    assert LogLevel.INFO.to_logging_level() == logging.INFO
    assert LogLevel.WARNING.to_logging_level() == logging.WARNING
    assert LogLevel.ERROR.to_logging_level() == logging.ERROR
    assert LogLevel.CRITICAL.to_logging_level() == logging.CRITICAL


def test_strip_markup():
    """Markup tags are removed; malformed markup falls back to raw text."""
    assert log.strip_markup("no markup") == "no markup"
    assert log.strip_markup("[bold]hi[/bold]") == "hi"
    assert log.strip_markup("\\[literal]") == "[literal]"
    assert log.strip_markup("[unclosed") == "[unclosed"


def test_deprecate_dedupes_and_renders(capsys):
    """Deprecation warnings render once per feature and call site."""
    for _ in range(2):
        log.deprecate(
            feature_name="TestFeature",
            reason="Use something else.",
            deprecation_version="0.1.0",
            removal_version="1.0",
        )
    out, _ = capsys.readouterr()
    assert out.count("DeprecationWarning: TestFeature has been deprecated") == 1
    assert "removed in 1.0" in out


def test_deprecate_json_extras(monkeypatch, capsys):
    """Deprecations carry structured metadata in JSON mode."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    log.deprecate(
        feature_name="JsonFeature",
        reason="Use something else.",
        deprecation_version="0.1.0",
        removal_version="1.0",
    )
    out, _ = capsys.readouterr()
    record = json.loads(out)
    assert record["feature_name"] == "JsonFeature"
    assert record["deprecation_version"] == "0.1.0"
    assert record["removal_version"] == "1.0"
    assert record["kind"] == "deprecation"


def test_timing_logs_at_debug(capsys):
    """The timing context manager emits a debug record with the duration."""
    log.set_log_level(LogLevel.DEBUG)
    with log.timing(logger, "block"):
        pass
    out, _ = capsys.readouterr()
    assert out.startswith("Debug: [timing] block: ")


def test_console_shims_delegate(capsys):
    """Legacy console helpers route through the pipeline and warn once."""
    console.info("legacy info")
    console.warn("legacy warn")
    console.error("legacy error")
    out, err = capsys.readouterr()
    out_lines = out.splitlines()
    assert "Info: legacy info" in out_lines
    assert "Warning: legacy warn" in out_lines
    assert "legacy error" in err.splitlines()
    assert "console.info has been deprecated" in out.replace("\n", " ")


def test_console_info_preserves_rich_print_kwargs(monkeypatch):
    """The deprecated info helper retains its Rich print contract."""
    rich_console = mock.Mock()
    monkeypatch.setattr(console, "_console", rich_console)
    monkeypatch.setattr(console, "_shim_deprecation", mock.Mock())

    console.info("[bold]message[/bold]", markup=False, soft_wrap=True)

    rich_console.print.assert_called_once_with(
        "[cyan]Info: [bold]message[/bold][/cyan]",
        markup=False,
        soft_wrap=True,
    )


def test_console_log_preserves_rich_log_rendering(monkeypatch):
    """The deprecated log helper still delegates to Rich Console.log."""
    rich_console = mock.Mock()
    monkeypatch.setattr(console, "_console", rich_console)
    monkeypatch.setattr(console, "_shim_deprecation", mock.Mock())

    console.log("message", justify="left")

    rich_console.log.assert_called_once_with("message", justify="left")


def test_console_debug_progress_preserves_file_log(monkeypatch):
    """Progress-bound debug output retains its legacy file-log behavior."""
    progress = mock.Mock()
    print_to_log_file = mock.Mock()
    monkeypatch.setattr(console, "_shim_deprecation", mock.Mock())
    monkeypatch.setattr(console, "is_debug", lambda: True)
    monkeypatch.setattr(console, "should_use_log_file_console", lambda: True)
    monkeypatch.setattr(console, "print_to_log_file", print_to_log_file)

    console.debug("message", progress=progress, markup=False)

    progress.console.print.assert_called_once_with(
        "[purple]Debug: message[/purple]", markup=False
    )
    print_to_log_file.assert_called_once_with(
        "[purple]Debug: message[/purple]", markup=False
    )


def test_console_deprecate_preserves_rich_print_kwargs(monkeypatch):
    """The legacy deprecation helper retains its Rich print contract."""
    rich_print = mock.Mock()
    monkeypatch.setattr(console, "print", rich_print)
    monkeypatch.setattr(console, "should_use_log_file_console", lambda: False)
    monkeypatch.setattr(
        console, "_get_first_non_framework_frame", lambda: None, raising=False
    )

    console.deprecate(
        feature_name="OldFeature",
        reason="Use NewFeature.",
        deprecation_version="0.9.9",
        removal_version="1.0",
        dedupe=False,
        markup=False,
    )

    rich_print.assert_called_once_with(
        "[yellow]DeprecationWarning: OldFeature has been deprecated in version "
        "0.9.9. Use NewFeature. It will be completely removed in 1.0.[/yellow]",
        level="warning",
        markup=False,
    )


def test_console_print_json_mode(monkeypatch, capsys):
    """console.print stays machine-readable in JSON mode."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    console.print("plain [bold]message[/bold]")
    out, _ = capsys.readouterr()
    record = json.loads(out)
    assert record["message"] == "plain message"
    assert record["level"] == "info"


def test_console_rule_json_mode(monkeypatch, capsys):
    """console.rule emits nothing in JSON mode."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    console.rule("Section")
    out, _ = capsys.readouterr()
    assert out == ""


def test_console_json_mode_preserves_severity(monkeypatch, capsys):
    """Legacy helpers keep their severity in the JSON stream."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    console.error("boom")
    console.warn("careful")
    console.success("done")
    out, err = capsys.readouterr()
    # Every line stays parseable; index by message so an unrelated record
    # (a deprecation warning from the helper itself) cannot break this.
    records = {
        record["message"]: record
        for record in map(json.loads, (out + err).splitlines())
    }
    assert records["boom"]["level"] == "error"
    assert records["Warning: careful"]["level"] == "warning"
    assert records["Success: done"]["level"] == "success"


def test_console_log_json_mode(monkeypatch, capsys):
    """console.log emits a JSON record instead of a timestamped rich line."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    console.log("compiling app")
    out, _ = capsys.readouterr()
    messages = [json.loads(line)["message"] for line in out.splitlines()]
    assert "compiling app" in messages


def test_console_print_table_json_mode(monkeypatch, capsys):
    """Tables stay in the machine-readable stream as structured rows."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    console.print_table([["app", "running"]], headers=["name", "status"])
    out, _ = capsys.readouterr()
    assert json.loads(out)["table"] == {
        "headers": ["name", "status"],
        "rows": [["app", "running"]],
    }


def test_poor_progress_json_mode(monkeypatch, capsys):
    """The fallback progress bar does not write plain text in JSON mode."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    progress = console.PoorProgress()
    progress.advance(progress.add_task("compile", total=2))
    out, _ = capsys.readouterr()
    assert json.loads(out)["message"] == "Progress: 1/2"


def _file_record(msg: str, *, rich: bool = False) -> logging.LogRecord:
    record = logging.LogRecord(
        name="reflex.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if rich:
        record.rich = True
    return record


def test_file_formatter_strips_markup_only_when_opted_in():
    """The file formatter strips markup from rich records and no others."""
    formatter = log._FileFormatter("[{asctime}] {levelname}: {message}", style="{")
    formatted = formatter.format(_file_record("[orange1]careful[/orange1]", rich=True))
    assert formatted.endswith(" WARNING: careful")
    assert formatted.startswith("[")
    assert formatter.format(_file_record("foo[bar]")).endswith(" WARNING: foo[bar]")


def test_log_file_path_honors_env(monkeypatch, tmp_path):
    """REFLEX_LOG_FILE overrides the default log file location."""
    log_file = tmp_path / "my.log"
    monkeypatch.setenv("REFLEX_LOG_FILE", str(log_file))
    assert log._log_file_path() == log_file


def test_log_file_path_creates_parent_of_configured_path(monkeypatch, tmp_path):
    """A configured path pointing into a new directory is made writable."""
    log_file = tmp_path / "nested" / "dir" / "my.log"
    monkeypatch.setenv("REFLEX_LOG_FILE", str(log_file))
    assert log._log_file_path() == log_file
    assert log_file.parent.is_dir()


def test_console_and_pipeline_share_one_log_file(monkeypatch, tmp_path):
    """Legacy console file output lands in the pipeline's log file."""
    log_file = tmp_path / "full.log"
    handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    monkeypatch.setattr(log, "_file_handler", lambda: handler)
    # Bypass the ``once`` cache so the console reopens against this handler.
    monkeypatch.setattr(
        console,
        "log_file_console",
        console.log_file_console.__wrapped__,  # pyright: ignore[reportFunctionMemberAccess]
    )
    reflex_logger = logging.getLogger("reflex")
    reflex_logger.addHandler(handler)
    try:
        console.print_to_log_file("from the legacy console")
        logger.warning("from the logging pipeline")
        handler.flush()
        contents = log_file.read_text(encoding="utf-8")
    finally:
        reflex_logger.removeHandler(handler)
        handler.close()
    assert "from the legacy console" in contents
    assert "from the logging pipeline" in contents


def _fresh_file_handler(
    monkeypatch, tmp_path: Path
) -> tuple[logging.FileHandler, Path]:
    """Create a real file handler on a temp path, bypassing the once cache.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: The pytest tmp_path fixture.

    Returns:
        The handler and the log file path it writes to.
    """
    log_file = tmp_path / "full.log"
    monkeypatch.setenv("REFLEX_LOG_FILE", str(log_file))
    handler = log._file_handler.__wrapped__()  # pyright: ignore[reportFunctionMemberAccess]
    monkeypatch.setattr(log, "_file_handler", lambda: handler)
    return handler, log_file


def test_file_handler_survives_external_dictconfig(monkeypatch, tmp_path):
    """Records keep landing in the log file after dictConfig closes the handler.

    granian's worker startup runs ``logging.config.dictConfig``, whose
    ``_clearExistingHandlers`` closes every fork-inherited handler; the file
    handler must reopen (appending, not truncating) instead of silently
    dropping every worker-side record.
    """
    import logging.config

    handler, log_file = _fresh_file_handler(monkeypatch, tmp_path)
    monkeypatch.setenv("REFLEX_ENABLE_FULL_LOGGING", "true")
    log.configure()
    try:
        logger.warning("before the worker dictConfig")
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": False})
        logger.warning("after the worker dictConfig")
    finally:
        logging.getLogger("reflex").removeHandler(handler)
        handler.close()
    contents = log_file.read_text(encoding="utf-8")
    assert "before the worker dictConfig" in contents
    assert "after the worker dictConfig" in contents


def test_log_file_console_targets_file_after_external_close(
    monkeypatch, tmp_path, capsys
):
    """A file console created after the handler was closed writes to the file.

    Before the fix, ``log_file_stream()`` returned the closed handler's
    ``None`` stream and rich fell back to stdout, leaking plain text into the
    ``--json`` output of granian workers.
    """
    handler, log_file = _fresh_file_handler(monkeypatch, tmp_path)
    monkeypatch.setattr(
        console,
        "log_file_console",
        console.log_file_console.__wrapped__,  # pyright: ignore[reportFunctionMemberAccess]
    )
    try:
        # What granian's post-fork dictConfig does to every existing handler.
        handler.close()
        console.print_to_log_file("worker record")
    finally:
        handler.close()
    out, _ = capsys.readouterr()
    assert out == ""
    assert "worker record" in log_file.read_text(encoding="utf-8")


def test_cached_log_file_console_survives_external_close(monkeypatch, tmp_path, capsys):
    """A file console created before the close keeps writing to the file."""
    handler, log_file = _fresh_file_handler(monkeypatch, tmp_path)
    file_console = console.log_file_console.__wrapped__()  # pyright: ignore[reportFunctionMemberAccess]
    monkeypatch.setattr(console, "log_file_console", lambda: file_console)
    try:
        console.print_to_log_file("record before close")
        handler.close()
        console.print_to_log_file("record after close")
    finally:
        handler.close()
    out, _ = capsys.readouterr()
    assert out == ""
    contents = log_file.read_text(encoding="utf-8")
    assert "record before close" in contents
    assert "record after close" in contents


def test_file_handler_truncates_previous_run(monkeypatch, tmp_path):
    """A fresh handler still truncates a file left over from a previous run."""
    log_file = tmp_path / "full.log"
    log_file.write_text("records from a previous run\n", encoding="utf-8")
    monkeypatch.setenv("REFLEX_LOG_FILE", str(log_file))
    handler = log._file_handler.__wrapped__()  # pyright: ignore[reportFunctionMemberAccess]
    handler.close()
    assert log_file.read_text(encoding="utf-8") == ""


def test_every_logging_package_root_is_registered():
    """Workspace packages that log must appear in PACKAGE_LOGGER_NAMES.

    Loggers do not propagate across top-level package names, so a package
    missing from the tuple silently escapes the reflex logger hierarchy.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    missing = {
        src.name
        for src in (repo_root / "packages").glob("*/src/*")
        if src.is_dir()
        and src.name not in log.PACKAGE_LOGGER_NAMES
        and any(
            "logging.getLogger(__name__)" in path.read_text(encoding="utf-8")
            for path in src.rglob("*.py")
        )
    }
    assert not missing, (
        f"add {sorted(missing)} to reflex_base.utils.log.PACKAGE_LOGGER_NAMES so "
        "their records join the reflex logger hierarchy"
    )


def test_bootstrap_parents_package_loggers_under_reflex(library_mode):
    """Every package logger chains to root through the ``reflex`` logger."""
    log.bootstrap()
    reflex_logger = logging.getLogger("reflex")
    assert reflex_logger.handlers == []
    assert reflex_logger.propagate is True
    for name in log.PACKAGE_LOGGER_NAMES:
        package_logger = logging.getLogger(name)
        assert package_logger.parent is reflex_logger
        assert package_logger.propagate is True
        assert package_logger.level == logging.NOTSET
    # Loggers created after bootstrap join the chain through their package root.
    deep = logging.getLogger("reflex_base.brand.new_child")
    parents = []
    node = deep
    while node := node.parent:
        parents.append(node)
    assert reflex_logger in parents
    assert parents[-1] is logging.getLogger()


def test_bootstrap_preserves_application_logger_config(library_mode):
    """An app's own level on a package logger survives bootstrap."""
    package_logger = logging.getLogger(log.PACKAGE_LOGGER_NAMES[0])
    package_logger.setLevel(logging.CRITICAL)
    try:
        log.bootstrap()
        assert package_logger.level == logging.CRITICAL
    finally:
        package_logger.setLevel(logging.NOTSET)


def test_bootstrap_never_attaches_sinks(monkeypatch):
    """Import-time bootstrap only reparents; sinks wait for ensure_configured.

    Attaching sinks needs ``reflex_base.environment``, which imports the
    component tree, so doing it at import time can close a circular import
    (``vars`` -> ``console`` -> ``log`` -> ``environment`` -> ``vars``).
    """
    monkeypatch.setenv(log._MANAGED_ENV_VAR, "true")
    log._reset()
    log.bootstrap()
    assert not log._configured
    assert log._console_handler() not in logging.getLogger("reflex").handlers
    log.ensure_configured()
    assert log._console_handler() in logging.getLogger("reflex").handlers


def test_managed_worker_can_import_vars_first():
    """A managed worker importing ``reflex_base.vars`` before anything else works."""
    subprocess.run(
        [sys.executable, "-c", "import reflex_base.vars"],
        check=True,
        env={**os.environ, log._MANAGED_ENV_VAR: "true"},
    )


def test_library_mode_records_propagate_to_root(library_mode, caplog):
    """Without the CLI, records reach root for the app (and pytest) to capture."""
    log.bootstrap()
    with caplog.at_level(logging.INFO, logger="reflex"):
        logger.info("through the root")
    assert "through the root" in caplog.text


def test_import_reflex_stays_light():
    """``import reflex`` must not drag in the log pipeline or rich.

    The pipeline self-bootstraps when its module first loads (which importing
    ``reflex_base.utils.console`` guarantees), so the root package import can
    stay lazy.
    """
    script = (
        "import sys\n"
        "import reflex\n"
        "assert 'reflex_base.utils.log' not in sys.modules, 'log loaded eagerly'\n"
        "assert 'rich' not in sys.modules, 'rich loaded eagerly'\n"
        "import logging\n"
        "import reflex_base.utils.console\n"
        "assert logging.getLogger('reflex_base').parent is logging.getLogger('reflex')\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True)


def test_traceback_file_paths_are_not_wrapped(monkeypatch, capsys):
    """Tracebacks print without word-wrapping so file paths survive intact."""
    monkeypatch.setattr(
        log, "_console_stderr", Console(stderr=True, highlight=False, width=40)
    )
    try:
        _ = 1 / 0
    except ZeroDivisionError:
        logger.exception("failed")
    _, err = capsys.readouterr()
    assert f'File "{__file__}"' in err


def test_deprecate_json_location_is_user_frame(monkeypatch, capsys):
    """Deprecation JSON records locate the user call site, not the framework."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    log.deprecate(
        feature_name="LocatedFeature",
        reason="Use something else.",
        deprecation_version="0.1.0",
        removal_version="1.0",
    )
    out, _ = capsys.readouterr()
    location = json.loads(out)["location"]
    path, _, lineno = location.rpartition(":")
    assert Path(path).name == Path(__file__).name
    assert lineno.isdigit()
