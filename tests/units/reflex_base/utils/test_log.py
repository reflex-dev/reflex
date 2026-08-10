"""Tests for the standard logging pipeline in reflex_base.utils.log."""

import json
import logging
from unittest import mock

import pytest
from reflex_base.constants import LogLevel
from reflex_base.utils import console, log

logger = logging.getLogger("reflex_base.tests.logs")


@pytest.fixture(autouse=True)
def clean_pipeline(monkeypatch):
    """Configure the pipeline at INFO with empty dedupe state for each test.

    Yields:
        None.
    """
    monkeypatch.delenv("REFLEX_LOG_JSON", raising=False)
    monkeypatch.delenv("REFLEX_LOGLEVEL", raising=False)
    monkeypatch.setattr(log, "_log_level", LogLevel.INFO)
    log._dedupe_filter().seen.clear()
    log.configure()
    yield
    monkeypatch.setattr(log, "_log_level", LogLevel.INFO)
    log._dedupe_filter().seen.clear()
    log.configure()


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


def test_markup_rendered_in_rich_mode(capsys):
    """Rich markup in messages is rendered, not shown literally."""
    logger.info("hello [bold]world[/bold]")
    out, _ = capsys.readouterr()
    assert out == "Info: hello world\n"


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


def test_json_mode(monkeypatch, capsys):
    """JSON mode emits one parseable record per line with markup stripped."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    logger.info("hello [bold]world[/bold]")
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
    for name in log.ROOT_LOGGER_NAMES:
        root = logging.getLogger(name)
        assert root.handlers.count(log._console_handler()) == 1
        assert log._json_handler() not in root.handlers


def test_configure_swaps_handler_in_json_mode(monkeypatch):
    """Switching JSON mode swaps the sink instead of stacking it."""
    monkeypatch.setenv("REFLEX_LOG_JSON", "true")
    log.configure()
    root = logging.getLogger("reflex")
    assert log._json_handler() in root.handlers
    assert log._console_handler() not in root.handlers


def test_configure_removes_file_handler_when_full_logging_is_disabled(monkeypatch):
    """Disabling full logging detaches its handler from every package logger."""
    handler = logging.NullHandler()
    monkeypatch.setattr(log, "_file_handler", lambda: handler)
    monkeypatch.setenv("REFLEX_ENABLE_FULL_LOGGING", "true")
    try:
        log.configure()
        assert handler in logging.getLogger("reflex").handlers

        monkeypatch.setenv("REFLEX_ENABLE_FULL_LOGGING", "false")
        log.configure()
        assert all(
            handler not in logging.getLogger(name).handlers
            for name in log.ROOT_LOGGER_NAMES
        )
    finally:
        for name in log.ROOT_LOGGER_NAMES:
            logger = logging.getLogger(name)
            if handler in logger.handlers:
                logger.removeHandler(handler)


def test_set_log_level_env_propagation(monkeypatch):
    """Changing the level exports REFLEX_LOGLEVEL for subprocesses."""
    log.set_log_level(LogLevel.DEBUG)
    import os

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


def test_file_formatter_strips_markup_and_formats_timestamp():
    """The file formatter strips markup and supports the configured timestamp."""
    formatter = log._StripMarkupFormatter(
        "[{asctime}] {levelname}: {message}", style="{"
    )
    record = logging.LogRecord(
        name="reflex.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="[orange1]careful[/orange1]",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert formatted.endswith(" WARNING: careful")
    assert formatted.startswith("[")


def test_log_file_path_honors_env(monkeypatch, tmp_path):
    """REFLEX_LOG_FILE overrides the default log file location."""
    log_file = tmp_path / "my.log"
    monkeypatch.setenv("REFLEX_LOG_FILE", str(log_file))
    assert log._log_file_path() == log_file


def test_every_logging_package_root_is_registered():
    """Workspace packages that log must appear in ROOT_LOGGER_NAMES.

    Loggers do not propagate across top-level package names, so a package
    missing from the tuple silently escapes the pipeline.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[4]
    missing = {
        src.name
        for src in (repo_root / "packages").glob("*/src/*")
        if src.is_dir()
        and src.name not in log.ROOT_LOGGER_NAMES
        and any(
            "logging.getLogger(__name__)" in path.read_text(encoding="utf-8")
            for path in src.rglob("*.py")
        )
    }
    assert not missing, (
        f"add {sorted(missing)} to reflex_base.utils.log.ROOT_LOGGER_NAMES so "
        "their records go through the reflex logging pipeline"
    )


def test_bootstrap_defers_configure_until_first_record(monkeypatch, capsys):
    """bootstrap() attaches sinks lazily and replays the triggering record."""
    monkeypatch.setattr(log, "_configured", False)
    for name in log.ROOT_LOGGER_NAMES:
        logging.getLogger(name).handlers.clear()

    log.bootstrap()
    assert not log._configured

    logger.info("first record")
    out, _ = capsys.readouterr()
    assert out == "Info: first record\n"
    assert log._configured
    for name in log.ROOT_LOGGER_NAMES:
        assert log._bootstrap_handler not in logging.getLogger(name).handlers
