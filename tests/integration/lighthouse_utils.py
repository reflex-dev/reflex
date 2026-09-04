"""Shared utilities for Lighthouse benchmarking."""

from __future__ import annotations

import json
import operator
import os
import re
import shlex
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pytest
from reflex_base import constants

from reflex.testing import chdir
from reflex.utils.templates import initialize_default_app

LIGHTHOUSE_RUN_ENV_VAR = "REFLEX_RUN_LIGHTHOUSE"
LIGHTHOUSE_COMMAND_ENV_VAR = "REFLEX_LIGHTHOUSE_COMMAND"
LIGHTHOUSE_CHROME_PATH_ENV_VAR = "REFLEX_LIGHTHOUSE_CHROME_PATH"
LIGHTHOUSE_CLI_PACKAGE = "lighthouse@13.1.0"
LIGHTHOUSE_COMMAND_PREP_TIMEOUT_SECONDS = 300
LIGHTHOUSE_RUN_TIMEOUT_SECONDS = 300
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
LIGHTHOUSE_CATEGORY_THRESHOLDS = {
    "performance": 0.56,
    "accessibility": 0.9,
    "best-practices": 0.9,
    "seo": 0.9,
}
LIGHTHOUSE_CATEGORIES = tuple(LIGHTHOUSE_CATEGORY_THRESHOLDS)
LIGHTHOUSE_LANDING_APP_NAME = "lighthouse_landing"
LIGHTHOUSE_FIXTURES_DIR = Path(__file__).parent / "lighthouse_fixtures"

LANDING_PAGE_SOURCE = '''\
"""A single-page landing page for Lighthouse benchmarking."""

import reflex as rx


class State(rx.State):
    """The app state."""


def navbar() -> rx.Component:
    return rx.el.nav(
        rx.container(
            rx.hstack(
                rx.hstack(
                    rx.image(
                        src="/logo.png",
                        width="28px",
                        height="28px",
                        alt="Acme logo",
                    ),
                    rx.heading("Acme", size="5", weight="bold"),
                    align="center",
                    spacing="2",
                ),
                rx.hstack(
                    rx.link("Features", href="#features", underline="none", size="3"),
                    rx.link("How It Works", href="#how-it-works", underline="none", size="3"),
                    rx.link("Pricing", href="#pricing", underline="none", size="3"),
                    rx.link("Testimonials", href="#testimonials", underline="none", size="3"),
                    spacing="5",
                    display={"base": "none", "md": "flex"},
                ),
                rx.button("Sign Up", size="2", high_contrast=True, radius="full"),
                justify="between",
                align="center",
                width="100%",
            ),
            size="4",
        ),
        style={
            "position": "sticky",
            "top": "0",
            "z_index": "50",
            "backdrop_filter": "blur(12px)",
            "border_bottom": "1px solid var(--gray-a4)",
            "padding_top": "12px",
            "padding_bottom": "12px",
        },
    )


def hero() -> rx.Component:
    return rx.section(
        rx.container(
            rx.vstack(
                rx.badge("Now in Public Beta", variant="surface", size="2", radius="full"),
                rx.heading(
                    "Ship products 10x faster ",
                    rx.text.span("with pure Python", color="var(--accent-9)"),
                    size="9",
                    weight="bold",
                    align="center",
                    line_height="1.1",
                ),
                rx.text(
                    "Stop wrestling with JavaScript. Build beautiful, performant "
                    "full-stack web apps using nothing but Python. "
                    "From prototype to production in record time.",
                    size="5",
                    align="center",
                    color="var(--gray-11)",
                    max_width="640px",
                ),
                rx.hstack(
                    rx.button(
                        rx.icon("arrow-right", size=16),
                        "Get Started Free",
                        size="4",
                        high_contrast=True,
                        radius="full",
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Watch Demo",
                        size="4",
                        variant="outline",
                        radius="full",
                    ),
                    spacing="3",
                ),
                rx.hstack(
                    rx.hstack(
                        rx.avatar(fallback="A", size="2", radius="full"),
                        rx.avatar(fallback="B", size="2", radius="full", style={"margin_left": "-8px"}),
                        rx.avatar(fallback="C", size="2", radius="full", style={"margin_left": "-8px"}),
                        rx.avatar(fallback="D", size="2", radius="full", style={"margin_left": "-8px"}),
                        spacing="0",
                    ),
                    rx.text(
                        "Trusted by 50,000+ developers worldwide",
                        size="2",
                        color="var(--gray-11)",
                    ),
                    align="center",
                    spacing="3",
                    pt="2",
                ),
                spacing="5",
                align="center",
                py="9",
            ),
            size="4",
        ),
    )


def stat_card(value: str, label: str) -> rx.Component:
    return rx.vstack(
        rx.heading(value, size="8", weight="bold", color="var(--accent-9)"),
        rx.text(label, size="3", color="var(--gray-11)"),
        align="center",
        spacing="1",
    )


def stats_bar() -> rx.Component:
    return rx.section(
        rx.container(
            rx.grid(
                stat_card("50K+", "Developers"),
                stat_card("10M+", "Apps Built"),
                stat_card("99.9%", "Uptime"),
                stat_card("150+", "Components"),
                columns="4",
                spacing="6",
                width="100%",
            ),
            size="4",
        ),
        style={
            "background": "var(--accent-2)",
            "border_top": "1px solid var(--gray-a4)",
            "border_bottom": "1px solid var(--gray-a4)",
        },
    )


def feature_card(icon_name: str, title: str, description: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.flex(
                rx.icon(icon_name, size=24, color="var(--accent-9)"),
                align="center",
                justify="center",
                style={
                    "width": "48px",
                    "height": "48px",
                    "border_radius": "12px",
                    "background": "var(--accent-3)",
                },
            ),
            rx.heading(title, size="4", weight="bold"),
            rx.text(description, size="3", color="var(--gray-11)", line_height="1.6"),
            spacing="3",
        ),
        size="3",
    )


def features() -> rx.Component:
    return rx.section(
        rx.container(
            rx.vstack(
                rx.badge("Features", variant="surface", size="2", radius="full"),
                rx.heading("Everything you need to build", size="8", weight="bold", align="center"),
                rx.text(
                    "A complete toolkit for modern web development, "
                    "designed for developers who value productivity.",
                    size="4",
                    color="var(--gray-11)",
                    align="center",
                    max_width="540px",
                ),
                rx.grid(
                    feature_card(
                        "code",
                        "Pure Python",
                        "Write your frontend and backend in Python. "
                        "No JavaScript, no HTML templates, no CSS files to manage.",
                    ),
                    feature_card(
                        "zap",
                        "Lightning Fast Refresh",
                        "See your changes reflected instantly. Hot reload keeps "
                        "your development loop tight and productive.",
                    ),
                    feature_card(
                        "layers",
                        "60+ Built-in Components",
                        "From data tables to charts, forms to navigation. "
                        "Production-ready components out of the box.",
                    ),
                    feature_card(
                        "shield-check",
                        "Type Safe",
                        "Full type safety across your entire stack. "
                        "Catch bugs at development time, not in production.",
                    ),
                    feature_card(
                        "database",
                        "Built-in State Management",
                        "Reactive state that syncs between frontend and backend "
                        "automatically. No boilerplate, no Redux.",
                    ),
                    feature_card(
                        "rocket",
                        "One-Command Deploy",
                        "Deploy to production with a single command. "
                        "Built-in hosting or bring your own infrastructure.",
                    ),
                    columns={"base": "1", "sm": "2", "lg": "3"},
                    spacing="5",
                    width="100%",
                ),
                spacing="5",
                align="center",
                py="6",
            ),
            size="4",
        ),
        id="features",
    )


def step_card(number: str, title: str, description: str) -> rx.Component:
    return rx.vstack(
        rx.flex(
            rx.text(number, size="5", weight="bold", color="white"),
            align="center",
            justify="center",
            style={
                "width": "48px",
                "height": "48px",
                "border_radius": "50%",
                "background": "var(--accent-9)",
                "flex_shrink": "0",
            },
        ),
        rx.heading(title, size="5", weight="bold"),
        rx.text(description, size="3", color="var(--gray-11)", line_height="1.6"),
        spacing="3",
        align="center",
        flex="1",
    )


def how_it_works() -> rx.Component:
    return rx.section(
        rx.container(
            rx.vstack(
                rx.badge("How It Works", variant="surface", size="2", radius="full"),
                rx.heading("Up and running in minutes", size="8", weight="bold", align="center"),
                rx.text(
                    "Three simple steps to go from idea to deployed application.",
                    size="4",
                    color="var(--gray-11)",
                    align="center",
                ),
                rx.grid(
                    step_card(
                        "1",
                        "Install & Initialize",
                        "Install the framework with pip and scaffold a new project "
                        "with a single command. Choose from starter templates.",
                    ),
                    step_card(
                        "2",
                        "Build Your App",
                        "Write components in pure Python. Use reactive state to "
                        "handle user interactions. Style with built-in themes.",
                    ),
                    step_card(
                        "3",
                        "Deploy",
                        "Push to production with one command. Automatic SSL, "
                        "CDN, and scaling handled for you.",
                    ),
                    columns={"base": "1", "md": "3"},
                    spacing="6",
                    width="100%",
                ),
                spacing="5",
                align="center",
                py="6",
            ),
            size="4",
        ),
        id="how-it-works",
        style={"background": "var(--accent-2)"},
    )


def pricing_card(
    name: str, price: str, period: str, description: str,
    features: list, highlighted: bool = False,
) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(name, size="5", weight="bold"),
            rx.hstack(
                rx.heading(price, size="8", weight="bold"),
                rx.text(period, size="3", color="var(--gray-11)", style={"align_self": "flex-end", "padding_bottom": "4px"}),
                align="end",
                spacing="1",
            ),
            rx.text(description, size="2", color="var(--gray-11)"),
            rx.separator(size="4"),
            rx.vstack(
                *[
                    rx.hstack(
                        rx.icon("check", size=16, color="var(--accent-9)"),
                        rx.text(f, size="2"),
                        spacing="2",
                        align="center",
                    )
                    for f in features
                ],
                spacing="2",
                width="100%",
            ),
            rx.button(
                "Get Started",
                size="3",
                width="100%",
                radius="full",
                variant="solid" if highlighted else "outline",
                high_contrast=highlighted,
            ),
            spacing="4",
            p="2",
        ),
        size="3",
        style={"border": "2px solid var(--accent-9)"} if highlighted else {},
    )


def pricing() -> rx.Component:
    return rx.section(
        rx.container(
            rx.vstack(
                rx.badge("Pricing", variant="surface", size="2", radius="full"),
                rx.heading("Simple, transparent pricing", size="8", weight="bold", align="center"),
                rx.text(
                    "No hidden fees. Start free and scale as you grow.",
                    size="4",
                    color="var(--gray-11)",
                    align="center",
                ),
                rx.grid(
                    pricing_card(
                        "Hobby",
                        "$0",
                        "/month",
                        "Perfect for side projects and learning.",
                        ["1 project", "Community support", "Basic analytics", "Custom domain"],
                    ),
                    pricing_card(
                        "Pro",
                        "$29",
                        "/month",
                        "For professionals shipping real products.",
                        ["Unlimited projects", "Priority support", "Advanced analytics", "Team collaboration", "Custom branding"],
                        highlighted=True,
                    ),
                    pricing_card(
                        "Enterprise",
                        "$99",
                        "/month",
                        "For teams that need full control.",
                        ["Everything in Pro", "SSO & SAML", "Dedicated infrastructure", "SLA guarantee", "24/7 phone support"],
                    ),
                    columns={"base": "1", "md": "3"},
                    spacing="5",
                    width="100%",
                ),
                spacing="5",
                align="center",
                py="6",
            ),
            size="4",
        ),
        id="pricing",
    )


def testimonial_card(quote: str, name: str, role: str, initials: str) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                *[rx.icon("star", size=14, color="var(--amber-9)") for _ in range(5)],
                spacing="1",
            ),
            rx.text(
                f"\\"{quote}\\"",
                size="3",
                style={"font_style": "italic"},
                color="var(--gray-12)",
                line_height="1.6",
            ),
            rx.hstack(
                rx.avatar(fallback=initials, size="3", radius="full"),
                rx.vstack(
                    rx.text(name, size="2", weight="bold"),
                    rx.text(role, size="1", color="var(--gray-11)"),
                    spacing="0",
                ),
                align="center",
                spacing="3",
            ),
            spacing="4",
        ),
        size="3",
    )


def testimonials() -> rx.Component:
    return rx.section(
        rx.container(
            rx.vstack(
                rx.badge("Testimonials", variant="surface", size="2", radius="full"),
                rx.heading("Loved by developers", size="8", weight="bold", align="center"),
                rx.text(
                    "See what developers around the world are saying.",
                    size="4",
                    color="var(--gray-11)",
                    align="center",
                ),
                rx.grid(
                    testimonial_card(
                        "This cut our development time in half. We shipped our MVP in two weeks instead of two months.",
                        "Sarah Chen",
                        "CTO at LaunchPad",
                        "SC",
                    ),
                    testimonial_card(
                        "Finally, a framework that lets me build full-stack apps without leaving Python. Game changer.",
                        "Marcus Johnson",
                        "Senior Engineer at DataFlow",
                        "MJ",
                    ),
                    testimonial_card(
                        "The component library is incredible. I spent zero time building UI primitives and all my time on business logic.",
                        "Priya Patel",
                        "Founder of MetricsDash",
                        "PP",
                    ),
                    columns={"base": "1", "md": "3"},
                    spacing="5",
                    width="100%",
                ),
                spacing="5",
                align="center",
                py="6",
            ),
            size="4",
        ),
        id="testimonials",
        style={"background": "var(--accent-2)"},
    )


def cta() -> rx.Component:
    return rx.section(
        rx.container(
            rx.card(
                rx.vstack(
                    rx.heading("Ready to build something amazing?", size="7", weight="bold", align="center"),
                    rx.text(
                        "Join thousands of developers shipping faster with pure Python. "
                        "Get started in under 60 seconds.",
                        size="4",
                        color="var(--gray-11)",
                        align="center",
                        max_width="480px",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.icon("arrow-right", size=16),
                            "Start Building",
                            size="4",
                            high_contrast=True,
                            radius="full",
                        ),
                        rx.button(
                            "Talk to Sales",
                            size="4",
                            variant="outline",
                            radius="full",
                        ),
                        spacing="3",
                    ),
                    spacing="5",
                    align="center",
                    py="6",
                ),
                size="5",
            ),
            size="4",
        ),
    )


def footer() -> rx.Component:
    return rx.el.footer(
        rx.container(
            rx.vstack(
                rx.separator(size="4"),
                rx.hstack(
                    rx.hstack(
                        rx.icon("hexagon", size=20, color="var(--accent-9)"),
                        rx.text("Acme", size="3", weight="bold"),
                        align="center",
                        spacing="2",
                    ),
                    rx.hstack(
                        rx.link("Privacy", href="#", underline="none", size="2", color="var(--gray-11)"),
                        rx.link("Terms", href="#", underline="none", size="2", color="var(--gray-11)"),
                        rx.link("Contact", href="#", underline="none", size="2", color="var(--gray-11)"),
                        spacing="4",
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                ),
                rx.text(
                    "\\u00a9 2026 Acme Inc. All rights reserved.",
                    size="1",
                    color="var(--gray-11)",
                ),
                spacing="4",
                py="6",
            ),
            size="4",
        ),
    )


def index() -> rx.Component:
    return rx.el.main(
        navbar(),
        hero(),
        stats_bar(),
        features(),
        how_it_works(),
        pricing(),
        testimonials(),
        cta(),
        footer(),
    )


app = rx.App()
app.add_page(
    index,
    title="Acme - Ship Products 10x Faster",
    description="Build beautiful full-stack web apps with pure Python. No JavaScript required.",
)
'''


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


def format_lighthouse_summary(
    report: dict[str, Any], report_path: Path, label: str = "blank prod app"
) -> str:
    """Format a compact Lighthouse score summary.

    Args:
        report: The parsed Lighthouse JSON report.
        report_path: The saved report path.
        label: A short label describing the app under test.

    Returns:
        A human-readable multi-line summary of Lighthouse scores.
    """
    lines = [
        f"Lighthouse summary for {label}",
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
    if shutil.which("pnpx") is not None:
        return ["pnpx", LIGHTHOUSE_CLI_PACKAGE]
    pytest.skip(
        "Lighthouse CLI is unavailable. "
        "Install `lighthouse`, make `npx` or `pnpx` available, "
        f"or set {LIGHTHOUSE_COMMAND_ENV_VAR}."
    )


def _format_subprocess_output(output: str | bytes | None) -> str:
    """Normalize subprocess output for failure messages.

    Args:
        output: The captured subprocess output.

    Returns:
        The output as a decoded string.
    """
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


@cache
def _prepare_lighthouse_command(command: tuple[str, ...]) -> tuple[str, ...]:
    """Warm package-runner-based Lighthouse commands before the benchmark.

    Args:
        command: The Lighthouse command prefix.

    Returns:
        The original command prefix.
    """
    if not command or command[0] not in {"npx", "pnpx"}:
        return command

    prepare_command = [*command, "--version"]
    try:
        subprocess.run(
            prepare_command,
            check=True,
            capture_output=True,
            text=True,
            timeout=LIGHTHOUSE_COMMAND_PREP_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as err:
        pytest.fail(
            "Lighthouse CLI preparation failed. "
            "If Lighthouse is not already installed, make sure the npm registry "
            f"is reachable or set {LIGHTHOUSE_COMMAND_ENV_VAR} to an installed CLI.\n"
            f"Command: {' '.join(prepare_command)}\n"
            f"stdout:\n{_format_subprocess_output(err.stdout)}\n"
            f"stderr:\n{_format_subprocess_output(err.stderr)}"
        )
    except subprocess.TimeoutExpired as err:
        pytest.fail(
            f"Lighthouse CLI preparation timed out after {err.timeout}s. "
            "If Lighthouse is not already installed, make sure the npm registry "
            f"is reachable or set {LIGHTHOUSE_COMMAND_ENV_VAR} to an installed CLI.\n"
            f"Command: {' '.join(prepare_command)}\n"
            f"stdout:\n{_format_subprocess_output(err.stdout)}\n"
            f"stderr:\n{_format_subprocess_output(err.stderr)}"
        )

    return command


def _get_lighthouse_target_url(url: str) -> str:
    """Convert bind-all URLs into loopback URLs that browser clients can reach.

    Args:
        url: The reported frontend URL.

    Returns:
        A client-reachable URL for Lighthouse.
    """
    parsed = urlsplit(url)
    replacement_host = {
        "0.0.0.0": "127.0.0.1",
        "::": "::1",
    }.get(parsed.hostname or "")
    if replacement_host is None:
        return url

    auth = ""
    if parsed.username is not None:
        auth = parsed.username
        if parsed.password is not None:
            auth += f":{parsed.password}"
        auth += "@"

    host = replacement_host
    if ":" in host:
        host = f"[{host}]"

    netloc = f"{auth}{host}"
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    return urlunsplit(parsed._replace(netloc=netloc))


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
        *_prepare_lighthouse_command(tuple(get_lighthouse_command())),
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
            timeout=LIGHTHOUSE_RUN_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as err:
        pytest.fail(
            "Lighthouse execution failed.\n"
            f"Command: {' '.join(command)}\n"
            f"stdout:\n{_format_subprocess_output(err.stdout)}\n"
            f"stderr:\n{_format_subprocess_output(err.stderr)}"
        )
    except subprocess.TimeoutExpired as err:
        pytest.fail(
            f"Lighthouse execution timed out after {err.timeout}s.\n"
            f"Command: {' '.join(command)}\n"
            f"stdout:\n{_format_subprocess_output(err.stdout)}\n"
            f"stderr:\n{_format_subprocess_output(err.stderr)}"
        )
    return json.loads(report_path.read_text())


def _ensure_lighthouse_app(
    root: Path, app_name: str, page_source: str | None = None
) -> None:
    """Initialize a Lighthouse benchmark app.

    Args:
        root: The app root directory.
        app_name: The app name for initialization.
        page_source: Optional custom page source to overwrite the generated page.
    """
    root.mkdir(parents=True, exist_ok=True)
    with chdir(root):
        initialize_default_app(app_name)
        shutil.copy(
            LIGHTHOUSE_FIXTURES_DIR / "images" / "logo.png",
            Path(constants.Dirs.APP_ASSETS) / "logo.png",
        )
        if page_source is not None:
            (Path(app_name) / f"{app_name}.py").write_text(page_source)


def _run_prod_lighthouse_benchmark(
    app_root: Path,
    report_path: Path,
    label: str,
) -> LighthouseBenchmarkResult:
    """Run Lighthouse against a Reflex app via ``reflex run --env prod``.

    Uses the real production code path so the benchmark automatically
    reflects any future changes to how Reflex serves apps in prod.

    Args:
        app_root: The app root to initialize or reuse.
        report_path: Where to save the Lighthouse JSON report.
        label: A short label for the summary output.

    Returns:
        A structured benchmark result.
    """
    report_path.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "reflex",
            "run",
            "--env",
            "prod",
            "--frontend-only",
            "--loglevel",
            "info",
        ],
        cwd=str(app_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for the frontend URL to appear in stdout.
    frontend_url = None
    captured_output: list[str] = []
    deadline = time.monotonic() + 120
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        captured_output.append(line)
        m = re.search(r"App running at:\s*(http\S+)", line)
        if m:
            frontend_url = m.group(1).rstrip("/")
            break

    if frontend_url is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        output = "".join(captured_output)
        pytest.fail(
            f"reflex run --env prod did not start within timeout for {label}\n"
            f"Captured output:\n{output}"
        )

    benchmark_url = _get_lighthouse_target_url(frontend_url)

    # Warmup request: ensure the server is fully ready before benchmarking.
    warmup_deadline = time.monotonic() + 30
    while time.monotonic() < warmup_deadline:
        try:
            urllib.request.urlopen(benchmark_url, timeout=5)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        proc.wait(timeout=10)
        pytest.fail(
            f"Warmup request to {benchmark_url} "
            f"(reported as {frontend_url}) never succeeded for {label}"
        )

    try:
        report = run_lighthouse(benchmark_url, report_path)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    failures = []
    for category_name, threshold in LIGHTHOUSE_CATEGORY_THRESHOLDS.items():
        score = report["categories"][category_name]["score"]
        if score is None or score < threshold:
            failures.append(category_name)

    return LighthouseBenchmarkResult(
        report=report,
        report_path=report_path,
        summary=format_lighthouse_summary(report, report_path, label=label),
        failures=failures,
    )


def run_landing_prod_lighthouse_benchmark(
    app_root: Path,
    report_path: Path,
) -> LighthouseBenchmarkResult:
    """Run Lighthouse against a single-page landing app in prod mode.

    Args:
        app_root: The app root to initialize or reuse.
        report_path: Where to save the Lighthouse JSON report.

    Returns:
        A structured benchmark result.
    """
    _ensure_lighthouse_app(app_root, LIGHTHOUSE_LANDING_APP_NAME, LANDING_PAGE_SOURCE)
    return _run_prod_lighthouse_benchmark(
        app_root=app_root,
        report_path=report_path,
        label="landing page prod app",
    )
