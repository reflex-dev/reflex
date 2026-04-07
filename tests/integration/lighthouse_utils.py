"""Shared utilities for Lighthouse benchmarking."""

from __future__ import annotations

import json
import operator
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from reflex.testing import AppHarnessProd, chdir
from reflex.utils.templates import initialize_default_app

LIGHTHOUSE_RUN_ENV_VAR = "REFLEX_RUN_LIGHTHOUSE"
LIGHTHOUSE_COMMAND_ENV_VAR = "REFLEX_LIGHTHOUSE_COMMAND"
LIGHTHOUSE_CHROME_PATH_ENV_VAR = "REFLEX_LIGHTHOUSE_CHROME_PATH"
LIGHTHOUSE_APP_ROOT_ENV_VAR = "REFLEX_LIGHTHOUSE_APP_ROOT"
LIGHTHOUSE_CLI_PACKAGE = "lighthouse@13.1.0"
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
LIGHTHOUSE_CATEGORY_THRESHOLDS = {
    "performance": 0.9,
    "accessibility": 0.9,
    "best-practices": 0.9,
    "seo": 0.9,
}
LIGHTHOUSE_CATEGORIES = tuple(LIGHTHOUSE_CATEGORY_THRESHOLDS)
LIGHTHOUSE_APP_NAME = "lighthouse_blank"


@dataclass(frozen=True)
class LighthouseBenchmarkResult:
    """A structured Lighthouse benchmark result."""

    report: dict[str, Any]
    report_path: Path
    summary: str
    failures: list[str]


def should_run_lighthouse() -> bool:
    """Check whether Lighthouse benchmarks are enabled.

    Returns:
        Whether Lighthouse benchmarks are enabled.
    """
    return os.environ.get(LIGHTHOUSE_RUN_ENV_VAR, "").lower() in TRUTHY_ENV_VALUES


def format_score(score: float | None) -> str:
    """Format a Lighthouse score for display.

    Args:
        score: The Lighthouse score in the 0-1 range.

    Returns:
        The score formatted as a 0-100 string.
    """
    if score is None:
        return "n/a"
    return str(round(score * 100))


def format_lighthouse_summary(report: dict[str, Any], report_path: Path) -> str:
    """Format a compact Lighthouse score summary.

    Args:
        report: The parsed Lighthouse JSON report.
        report_path: The saved report path.

    Returns:
        A human-readable multi-line summary of Lighthouse scores.
    """
    lines = [
        "Lighthouse summary for blank prod app",
        "",
        f"{'Category':<16} {'Score':>5} {'Target':>6} {'Status':>6}",
        f"{'-' * 16} {'-' * 5} {'-' * 6} {'-' * 6}",
    ]
    failure_details = []

    for category_name, threshold in LIGHTHOUSE_CATEGORY_THRESHOLDS.items():
        score = report["categories"][category_name]["score"]
        passed = score is not None and score >= threshold
        lines.append(
            f"{category_name:<16} {format_score(score):>5} {round(threshold * 100):>6} {'PASS' if passed else 'FAIL':>6}"
        )
        if not passed:
            failure_details.append(
                f"- {category_name}: {get_category_failure_details(report, category_name)}"
            )

    lines.extend([
        "",
        f"Report: {report_path}",
    ])
    if failure_details:
        lines.extend([
            "",
            "Lowest-scoring audits:",
            *failure_details,
        ])

    return "\n".join(lines)


def get_lighthouse_command() -> list[str]:
    """Resolve the Lighthouse CLI command.

    Returns:
        The command prefix used to invoke Lighthouse.
    """
    if command := os.environ.get(LIGHTHOUSE_COMMAND_ENV_VAR):
        return shlex.split(command)
    if shutil.which("lighthouse") is not None:
        return ["lighthouse"]
    if shutil.which("npx") is not None:
        return ["npx", "--yes", LIGHTHOUSE_CLI_PACKAGE]
    pytest.skip(
        "Lighthouse CLI is unavailable. "
        f"Install `lighthouse`, make `npx` available, or set {LIGHTHOUSE_COMMAND_ENV_VAR}."
    )


def get_chrome_path() -> str:
    """Resolve the Chromium executable used by Lighthouse.

    Returns:
        The path to the Chromium executable Lighthouse should launch.
    """
    if chrome_path := os.environ.get(LIGHTHOUSE_CHROME_PATH_ENV_VAR):
        resolved_path = Path(chrome_path).expanduser()
        if not resolved_path.exists():
            pytest.skip(
                f"{LIGHTHOUSE_CHROME_PATH_ENV_VAR} points to a missing binary: {resolved_path}"
            )
        return str(resolved_path)

    sync_api = pytest.importorskip(
        "playwright.sync_api",
        reason="Playwright is required to locate a Chromium binary for Lighthouse.",
    )
    candidates: list[Path] = []
    with sync_api.sync_playwright() as playwright:
        candidates.append(Path(playwright.chromium.executable_path))

    browser_cache_dirs = [
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "Library" / "Caches" / "ms-playwright",
    ]
    if local_app_data := os.environ.get("LOCALAPPDATA"):
        browser_cache_dirs.append(Path(local_app_data) / "ms-playwright")

    browser_glob_patterns = [
        "chromium_headless_shell-*/*/chrome-headless-shell",
        "chromium-*/*/chrome",
        "chromium-*/*/chrome.exe",
        "chromium-*/*/Chromium.app/Contents/MacOS/Chromium",
    ]
    for cache_dir in browser_cache_dirs:
        if not cache_dir.exists():
            continue
        for pattern in browser_glob_patterns:
            candidates.extend(sorted(cache_dir.glob(pattern), reverse=True))

    for resolved_path in candidates:
        if resolved_path.exists():
            return str(resolved_path)

    pytest.skip(
        "Playwright Chromium is not installed. "
        "Run `uv run playwright install chromium --only-shell` first."
    )


def get_category_failure_details(report: dict[str, Any], category_name: str) -> str:
    """Summarize the lowest-scoring weighted audits in a Lighthouse category.

    Args:
        report: The parsed Lighthouse JSON report.
        category_name: The category to summarize.

    Returns:
        A short summary of the lowest-scoring weighted audits.
    """
    category = report["categories"][category_name]
    audits = report["audits"]
    failing_audits: list[tuple[float, str]] = []

    for audit_ref in category["auditRefs"]:
        if audit_ref["weight"] <= 0:
            continue
        audit = audits[audit_ref["id"]]
        score = audit.get("score")
        if score is None or score >= 1:
            continue
        failing_audits.append((score, audit["title"]))

    if not failing_audits:
        return "no weighted audit details"

    failing_audits.sort(key=operator.itemgetter(0))
    return ", ".join(
        f"{title} ({format_score(score)})" for score, title in failing_audits[:3]
    )


def run_lighthouse(url: str, report_path: Path) -> dict[str, Any]:
    """Run Lighthouse against a URL and return the parsed JSON report.

    Args:
        url: The URL to audit.
        report_path: Where to save the JSON report.

    Returns:
        The parsed Lighthouse JSON report.
    """
    command = [
        *get_lighthouse_command(),
        url,
        "--output=json",
        f"--output-path={report_path}",
        f"--chrome-path={get_chrome_path()}",
        f"--only-categories={','.join(LIGHTHOUSE_CATEGORIES)}",
        "--quiet",
        "--chrome-flags=--headless=new --no-sandbox --disable-dev-shm-usage",
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.CalledProcessError as err:
        pytest.fail(
            "Lighthouse execution failed.\n"
            f"Command: {' '.join(command)}\n"
            f"stdout:\n{err.stdout}\n"
            f"stderr:\n{err.stderr}"
        )
    return json.loads(report_path.read_text())


def get_local_cached_app_root() -> Path:
    """Get the local cached app root used by the CLI runner.

    Returns:
        The local cached app root path.
    """
    return Path(".states") / LIGHTHOUSE_APP_NAME


def get_env_or_default_app_root(default_root: Path) -> Path:
    """Resolve the app root, optionally overridden by an environment variable.

    Args:
        default_root: The fallback app root.

    Returns:
        The resolved app root path.
    """
    if app_root := os.environ.get(LIGHTHOUSE_APP_ROOT_ENV_VAR):
        return Path(app_root).expanduser()
    return default_root


def ensure_blank_lighthouse_app(root: Path) -> None:
    """Ensure the cached blank benchmark app exists.

    Args:
        root: The app root directory.
    """
    root.mkdir(parents=True, exist_ok=True)
    with chdir(root):
        if not Path("rxconfig.py").exists():
            initialize_default_app(LIGHTHOUSE_APP_NAME)


def run_blank_prod_lighthouse_benchmark(
    app_root: Path,
    report_path: Path,
) -> LighthouseBenchmarkResult:
    """Run Lighthouse against the stock blank Reflex app in prod mode.

    Args:
        app_root: The app root to initialize or reuse.
        report_path: Where to save the Lighthouse JSON report.

    Returns:
        A structured benchmark result.
    """
    ensure_blank_lighthouse_app(app_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with AppHarnessProd.create(root=app_root, app_name=LIGHTHOUSE_APP_NAME) as harness:
        assert harness.frontend_url is not None
        report = run_lighthouse(harness.frontend_url, report_path)

    failures = []
    for category_name, threshold in LIGHTHOUSE_CATEGORY_THRESHOLDS.items():
        score = report["categories"][category_name]["score"]
        if score is None or score < threshold:
            failures.append(category_name)

    return LighthouseBenchmarkResult(
        report=report,
        report_path=report_path,
        summary=format_lighthouse_summary(report, report_path),
        failures=failures,
    )
