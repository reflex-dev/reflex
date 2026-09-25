"""The ``reflex-bench`` command line interface.

The CLI is the only code path: CI runs the same commands and only adds output
targets. When ``CI=true`` the output is plain (no colors, no live progress) and
``--fail-on`` defaults to ``regression``; nothing else changes.

Exit codes: 0 ok, 1 harness error (including every benchmark failing),
2 regression found with ``--fail-on regression``, 3 inconclusive result with
``--fail-on-inconclusive``.
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import sys
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.status import Status
from rich.text import Text

from reflex_bench import ab, subjects
from reflex_bench import compare as comparing
from reflex_bench.budgets import budgets_command
from reflex_bench.collectors import cgroup
from reflex_bench.context import Subject, installed_version
from reflex_bench.machine import Check, checks, collect, warning_count
from reflex_bench.registry import SUITES, Benchmark, discover, parse_overrides, select
from reflex_bench.report.bmf import to_bmf
from reflex_bench.report.format import DOT, WARN, format_value
from reflex_bench.report.markdown import render_comparison as markdown_comparison
from reflex_bench.report.table import (
    make_console,
    render_comparison,
    render_header,
    render_run,
    render_samples,
)
from reflex_bench.scheduler import Event, Policy, Scheduler, plan, utc_now
from reflex_bench.schema import (
    FAIL_ON,
    RUN_KINDS,
    SCHEMA_ID,
    CiDoc,
    FailOn,
    ResultDoc,
    RunKind,
    SchemaError,
    dump,
    dumps,
    load,
)
from reflex_bench.store import (
    autosave,
    bench_home,
    check_baseline_name,
    resolve_baseline,
    save_baseline,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REGRESSION = 2
EXIT_INCONCLUSIVE = 3
EXIT_INTERRUPTED = 130
# Subject venvs default to the harness's Python, which the workspace runs on.
DEFAULT_PYTHON = f"{sys.version_info.major}.{sys.version_info.minor}"
_ARGV = "reflex_bench.argv"
_CHECK_ICONS = {"ok": "\N{CHECK MARK}", "warn": WARN, "info": DOT}
_AGE = re.compile(r"(\d+)([dhm])")
_AGE_UNITS = {"d": "days", "h": "hours", "m": "minutes"}


def in_ci() -> bool:
    """Detect a CI run.

    Returns:
        Whether the ``CI`` environment variable is ``true``.
    """
    return os.environ.get("CI", "").strip().lower() == "true"


class _Group(click.Group):
    """The command group: records the raw arguments and owns the exit codes."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Remember the arguments for the result document.

        Args:
            ctx: The click context.
            args: The raw arguments.

        Returns:
            The arguments left for the subcommand.
        """
        ctx.meta[_ARGV] = list(args)
        return super().parse_args(ctx, args)

    def main(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        **extra: Any,
    ) -> None:
        """Run the CLI and exit with the command's exit code.

        Usage errors exit with 1 like other harness errors, keeping 2 and 3 for
        regressions and inconclusive results.

        Args:
            args: The arguments; defaults to ``sys.argv``.
            prog_name: The program name.
            complete_var: The shell completion variable.
            standalone_mode: Ignored; the CLI always exits.
            **extra: Passed to the click context.
        """
        try:
            code = super().main(
                args, prog_name, complete_var, standalone_mode=False, **extra
            )
        except click.ClickException as exc:
            exc.show()
            code = EXIT_ERROR
        except click.Abort:
            click.echo("interrupted", err=True)
            code = EXIT_INTERRUPTED
        sys.exit(code if isinstance(code, int) else EXIT_OK)


@click.group(cls=_Group, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="reflex-bench", prog_name="reflex-bench")
def cli() -> None:
    """Macro benchmarks for Reflex: run, store, compare and report."""


def _relative(path: Path) -> str:
    """Show a path relative to the working directory when it is inside it.

    Args:
        path: The path.

    Returns:
        The path to print.
    """
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _duration(seconds: float) -> str:
    """Format a rough duration.

    Args:
        seconds: The duration.

    Returns:
        E.g. ``0.3 s``, ``12 s`` or ``3.5 min``.
    """
    if seconds < 10:
        return f"{seconds:.1f} s"
    if seconds < 120:
        return f"{seconds:.0f} s"
    return f"{seconds / 60:.1f} min"


def _estimate(bench: Benchmark, policy: Policy) -> float:
    """Estimate how long one instance runs under a policy.

    Args:
        bench: The benchmark.
        policy: The policy.

    Returns:
        Seconds, from the benchmark's ``estimate`` per sample.
    """
    runs = policy.runs or (1 if bench.exact else policy.auto_runs(bench.estimate))
    return (bench.warmup + runs) * bench.estimate


def _print_rows(console: Console, rows: Sequence[Sequence[str]]) -> None:
    """Print rows in aligned columns, the first one (the titles) in bold.

    Args:
        console: Where to print.
        rows: The titles, then one row per item.
    """
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        line = "   ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        )
        console.print(Text(line.rstrip(), style="bold" if index == 0 else ""))


@cli.command("list")
@click.argument("filters", nargs=-1)
@click.option("--suite", type=click.Choice(SUITES), help="A named selection.")
def list_command(filters: tuple[str, ...], suite: str | None) -> int:
    """List benchmarks: id with params, kind, metrics, suites and estimated duration.

    FILTERS are globs on the benchmark id, e.g. 'lifecycle.*'. Self-tests are
    listed with --suite selftest.

    Args:
        filters: Globs on the benchmark id.
        suite: A named selection.

    Returns:
        The exit code.
    """
    console = make_console(plain=in_ci())
    planned = plan(select(discover().values(), filters, suite), suite=suite)
    if not planned:
        hint = "" if suite else " (self-tests are listed with --suite selftest)"
        console.print(Text(f"no benchmarks selected{hint}"))
        return EXIT_OK
    policy = Policy()
    rows = [["id", "kind", "metrics", "suites", "estimate"]]
    total = 0.0
    for item in planned:
        bench = item.benchmark
        seconds = _estimate(bench, policy)
        total += seconds
        metrics = ", ".join(
            f"{name} ({metric.unit}{', exact' if metric.assume == 'exact' else ''})"
            for name, metric in bench.metrics.items()
        )
        rows.append([
            item.name,
            bench.kind,
            metrics,
            ",".join(bench.suites),
            f"~{_duration(seconds)}",
        ])
    _print_rows(console, rows)
    console.print(
        Text(
            f"{len(planned)} benchmarks {DOT} ~{_duration(total)} estimated with default settings"
        )
    )
    return EXIT_OK


def _ci_info() -> CiDoc:
    """Describe the CI run from its environment.

    Returns:
        The provider, run id, run URL and runner name.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        run_id = os.environ.get("GITHUB_RUN_ID")
        server = os.environ.get("GITHUB_SERVER_URL")
        repository = os.environ.get("GITHUB_REPOSITORY")
        return {
            "provider": "github",
            "run_id": run_id,
            "url": f"{server}/{repository}/actions/runs/{run_id}"
            if run_id and server and repository
            else None,
            "runner": os.environ.get("RUNNER_NAME"),
        }
    return {"provider": "unknown", "run_id": None, "url": None, "runner": None}


class _Progress:
    """Reports progress: NDJSON events, a live status line, or one line per benchmark."""

    def __init__(self, console: Console, *, live: bool, ndjson: bool) -> None:
        """Choose the progress style.

        Args:
            console: Where human output goes.
            live: Show a live status line instead of one line per benchmark.
            ndjson: Also write every event as a JSON line to standard output.
        """
        self.console = console
        self.ndjson = ndjson
        self.status: Status | None = console.status("") if live else None
        self._started = 0.0

    def __enter__(self) -> _Progress:
        """Start the live status line, if any.

        Returns:
            The progress reporter.
        """
        if self.status is not None:
            self.status.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop the live status line, if any.

        Args:
            *exc_info: The exception being raised, if any.
        """
        if self.status is not None:
            self.status.stop()

    def emit(self, event: Event) -> None:
        """Handle one event.

        Args:
            event: The event.
        """
        if self.ndjson:
            click.echo(json.dumps(event, separators=(",", ":")))
        kind = event["event"]
        if kind == "benchmark_start":
            self._started = time.perf_counter()
        if self.status is not None and kind in {"benchmark_start", "sample"}:
            if kind == "sample":
                done = (
                    f"warmup {event['index'] + 1}"
                    if event["warmup"]
                    else (f"{event['timed']}/{event['target'] or '?'}")
                )
            else:
                done = f"{event['index'] + 1}/{event['total']}"
            elapsed = time.perf_counter() - self._started
            self.status.update(f"{event['id']} {done} {DOT} {elapsed:.1f} s")
        elif self.status is None and kind == "benchmark_end":
            samples = "sample" if event["n"] == 1 else "samples"
            self.console.print(
                Text(
                    f"[{event['index'] + 1}/{event['total']}] {event['id']} {event['status']}"
                    f" {DOT} {event['n']} {samples} {DOT} {event['elapsed_s']:.1f} s"
                )
            )


def _new_doc(
    subject: Subject,
    policy: Policy,
    seed: int,
    argv: list[str],
    kind: RunKind | None,
) -> ResultDoc:
    """Create the result document of a run, before any benchmark runs.

    Args:
        subject: The reflex installation under test.
        policy: The run policy.
        seed: The invocation seed.
        argv: The command line arguments.
        kind: The run kind; defaults to ``local`` or ``ci``.

    Returns:
        The document with no benchmarks.
    """
    ci = in_ci()
    return {
        "schema": SCHEMA_ID,
        "tool": {
            "name": "reflex-bench",
            "version": installed_version("reflex-bench") or "unknown",
        },
        "invocation": {
            "id": str(uuid.uuid4()),
            "argv": argv,
            "started_at": utc_now("seconds"),
            "duration_s": 0.0,
            "mode": "ci" if ci else "local",
            "kind": kind or ("ci" if ci else "local"),
            "ci": _ci_info() if ci else None,
            "rng_seed": seed,
        },
        "subjects": {"A": subject.to_doc()},
        "machine": collect(python_version=subject.python_version),
        "fixture": None,
        "policy": policy.to_doc(),
        "benchmarks": [],
    }


def _resolve_fail_on(option: FailOn | None) -> FailOn:
    """Apply the environment-dependent default of ``--fail-on``.

    Args:
        option: The ``--fail-on`` value, if given.

    Returns:
        The option, else ``regression`` when ``CI=true`` and ``never`` otherwise.
    """
    return option or ("regression" if in_ci() else "never")


def _exit_code(
    doc: ResultDoc, fail_on: FailOn, fail_on_inconclusive: bool, compared: bool
) -> int:
    """Decide the exit code of a run or comparison.

    An entry that started failing in head counts as a regression, and as a
    comparison made even when no metric could be compared.

    Args:
        doc: The result, annotated when compared.
        fail_on: ``regression`` or ``never``.
        fail_on_inconclusive: Whether inconclusive results fail.
        compared: Whether a comparison was requested.

    Returns:
        The exit code.
    """
    statuses = {entry["status"] for entry in doc["benchmarks"]}
    if statuses & {"failed", "timeout"} and "ok" not in statuses:
        return EXIT_ERROR
    failed = comparing.failed_in_head(doc)
    if compared and not failed and not comparing.rows(doc):
        return EXIT_ERROR
    counts = comparing.verdict_counts(doc)
    if fail_on == "regression" and (counts["regressed"] or failed):
        return EXIT_REGRESSION
    if fail_on_inconclusive and counts["inconclusive"]:
        return EXIT_INCONCLUSIVE
    return EXIT_OK


def _fail_options(command: Any) -> Any:
    """Add the ``--fail-on`` options shared by ``run`` and ``compare``.

    Args:
        command: The click command function.

    Returns:
        The decorated function.
    """
    command = click.option(
        "--fail-on-inconclusive",
        is_flag=True,
        help="Exit with 3 when any comparison is inconclusive.",
    )(command)
    return click.option(
        "--fail-on",
        type=click.Choice(FAIL_ON),
        help="Exit with 2 on a regression. Default: never locally, regression when CI=true.",
    )(command)


def _stats_options(command: Any) -> Any:
    """Add the ``--threshold`` and ``--alpha`` options shared by ``run`` and ``compare``.

    Args:
        command: The click command function.

    Returns:
        The decorated function.
    """
    command = click.option(
        "--alpha",
        type=click.FloatRange(0, 1, min_open=True, max_open=True),
        default=0.01,
        show_default=True,
        help="Significance level (Holm-corrected across metrics).",
    )(command)
    return click.option(
        "--threshold",
        type=click.FloatRange(min=0),
        default=3.0,
        show_default=True,
        metavar="PCT",
        help="Practical threshold for verdicts, in percent.",
    )(command)


def _check_spec(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Validate a subject spec option (``--reflex``, ``--base``, ``--head``).

    Args:
        ctx: The click context.
        param: The option.
        value: The spec, if given.

    Returns:
        The spec, unchanged.

    Raises:
        BadParameter: When it is not a subject spec.
    """
    if value is not None:
        try:
            subjects.parse_spec(value)
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc
    return value


def _instance_options(command: Any) -> Any:
    """Add the options ``run`` and ``ab`` share: parameters, timeouts, seed and Python.

    Args:
        command: The click command function.

    Returns:
        The decorated function.
    """
    command = click.option(
        "--python",
        default=DEFAULT_PYTHON,
        show_default=True,
        help="Python of subject venvs; defaults to the harness's, which the"
        " workspace runs on.",
    )(command)
    command = click.option(
        "--keep", is_flag=True, help="Keep each benchmark's work directory."
    )(command)
    command = click.option(
        "--seed",
        type=click.IntRange(min=0),
        help="RNG seed. Default: random (always recorded).",
    )(command)
    command = click.option(
        "--timeout",
        type=click.FloatRange(min=0, min_open=True),
        metavar="SECONDS",
        help="Per-sample timeout. Default: per benchmark.",
    )(command)
    return click.option(
        "--param",
        "params",
        multiple=True,
        metavar="KEY=VALUE",
        help="Restrict or override a parameter.",
    )(command)


def _output_options(command: Any) -> Any:
    """Add the options ``run`` and ``ab`` share for storing and streaming results.

    Args:
        command: The click command function.

    Returns:
        The decorated function.
    """
    command = click.option(
        "--ndjson",
        is_flag=True,
        help="Progress events as NDJSON on stdout; human output on stderr.",
    )(command)
    command = click.option(
        "--json",
        "json_path",
        type=click.Path(dir_okay=False, path_type=Path),
        help="Also write the result JSON here.",
    )(command)
    command = click.option(
        "--save-as", metavar="NAME", help="Also store the result as a named baseline."
    )(command)
    return click.option(
        "--save/--no-save", default=True, show_default=True, help="Autosave the result."
    )(command)


def _select(
    filters: Sequence[str], suite: str | None, overrides: Mapping[str, str]
) -> list[Benchmark]:
    """Select the benchmarks to run and check the ``--param`` overrides against them.

    Args:
        filters: Globs on the benchmark id.
        suite: A named selection.
        overrides: The ``--param`` overrides.

    Returns:
        The selected benchmarks.

    Raises:
        UsageError: When nothing matches or no selected benchmark takes a
            ``--param``.
    """
    benchmarks = select(discover().values(), filters, suite)
    if not benchmarks:
        msg = (
            "no benchmark matches"
            + (f" {' '.join(filters)}" if filters else "")
            + (f" in suite {suite}" if suite else "")
        )
        raise click.UsageError(msg)
    known = set().union(*(bench.param_names for bench in benchmarks))
    if unknown := sorted(overrides.keys() - known):
        msg = f"unknown --param {', '.join(unknown)}; the selected benchmarks take: {', '.join(sorted(known)) or 'none'}"
        raise click.UsageError(msg)
    return benchmarks


def _resolve(spec: str, python: str, home: Path, console: Console) -> Subject:
    """Build or reuse the environment of a subject, printing what happens.

    Args:
        spec: The subject spec.
        python: The Python of subject venvs.
        home: The bench home.
        console: Where progress goes.

    Returns:
        The subject.

    Raises:
        ClickException: When its environment cannot be built.
    """
    try:
        return subjects.resolve(
            spec,
            python=python,
            home=home,
            echo=lambda message: console.print(Text(message)),
        )
    except subjects.SubjectError as exc:
        raise click.ClickException(str(exc)) from exc


def _finish(
    console: Console,
    doc: ResultDoc,
    home: Path,
    *,
    save: bool,
    save_as: str | None,
    json_path: Path | None,
    ndjson: bool,
    kept: Sequence[Path],
    compared: bool,
) -> int:
    """Store a result, list what was written or kept and decide the exit code.

    Args:
        console: Where human output goes.
        doc: The result.
        home: The bench home.
        save: Whether to autosave the result.
        save_as: A baseline name to also store the result as.
        json_path: A file to also write the result to.
        ndjson: Whether to end the NDJSON stream with a ``run_end`` event.
        kept: The work directories that were kept.
        compared: Whether the result was compared.

    Returns:
        The exit code; ``EXIT_INTERRUPTED`` for an interrupted run.
    """
    saved = []
    if save:
        saved.append(autosave(doc, home))
    if save_as and doc.get("interrupted"):
        console.print(Text(f"interrupted: not saved as baseline {save_as}"))
    elif save_as:
        saved.append(save_baseline(doc, save_as, home))
    if json_path is not None:
        dump(doc, json_path)
        saved.append(json_path)
    if saved:
        console.print()
    for path in saved:
        console.print(Text(f"saved {_relative(path)}"))
    for path in kept:
        console.print(Text(f"kept {path}"))
    policy = doc["policy"]
    code = (
        EXIT_INTERRUPTED
        if doc.get("interrupted")
        else _exit_code(
            doc, policy["fail_on"], policy["fail_on_inconclusive"], compared=compared
        )
    )
    if ndjson:
        click.echo(
            json.dumps(
                {
                    "event": "run_end",
                    "exit_code": code,
                    "statuses": Counter(entry["status"] for entry in doc["benchmarks"]),
                    "verdicts": comparing.verdict_counts(doc),
                    "saved": [str(path) for path in saved],
                },
                separators=(",", ":"),
            )
        )
    return code


@cli.command()
@click.argument("filters", nargs=-1)
@click.option("--suite", type=click.Choice(SUITES), help="A named selection.")
@click.option(
    "--reflex",
    default="workspace",
    show_default=True,
    metavar="SPEC",
    callback=_check_spec,
    help="The reflex to measure: workspace, a PyPI version (0.8.23), git:<ref> or path:<dir>.",
)
@click.option(
    "--runs",
    type=click.IntRange(min=1),
    help="Fixed run count (overrides the auto rule).",
)
@click.option("--min-runs", type=click.IntRange(min=1), default=10, show_default=True)
@click.option(
    "--max-runs",
    type=click.IntRange(min=1),
    help="The most runs of the automatic rule. Default: max(30, --min-runs).",
)
@click.option(
    "--min-time",
    type=click.FloatRange(min=0),
    default=30.0,
    show_default=True,
    metavar="SECONDS",
)
@click.option(
    "--warmup", type=click.IntRange(min=0), help="Untimed runs. Default: per benchmark."
)
@click.option(
    "--baseline", metavar="NAME|FILE", help="Compare with a baseline after the run."
)
@_instance_options
@_stats_options
@_fail_options
@_output_options
@click.option("--smoke", is_flag=True, help="1 run, no warmup, no statistics.")
@click.option(
    "--kind",
    type=click.Choice(RUN_KINDS),
    help="The run kind recorded in the result. Default: local, or ci when CI=true.",
)
@click.pass_context
def run(
    ctx: click.Context,
    filters: tuple[str, ...],
    suite: str | None,
    reflex: str,
    runs: int | None,
    min_runs: int,
    max_runs: int | None,
    min_time: float,
    warmup: int | None,
    baseline: str | None,
    params: tuple[str, ...],
    timeout: float | None,
    seed: int | None,
    keep: bool,
    python: str,
    threshold: float,
    alpha: float,
    fail_on: FailOn | None,
    fail_on_inconclusive: bool,
    save: bool,
    save_as: str | None,
    json_path: Path | None,
    ndjson: bool,
    smoke: bool,
    kind: RunKind | None,
) -> int:
    """Run benchmarks and print, store and optionally compare the results.

    FILTERS are globs on the benchmark id, e.g. 'lifecycle.*'.

    Args:
        ctx: The click context.
        filters: Globs on the benchmark id.
        suite: A named selection.
        reflex: The subject spec.
        runs: A fixed run count.
        min_runs: The fewest runs of the automatic rule.
        max_runs: The most runs of the automatic rule; ``None`` for
            ``max(30, min_runs)``.
        min_time: The measuring time the automatic rule aims for.
        warmup: Untimed runs.
        baseline: A baseline to compare with.
        params: ``KEY=VALUE`` parameter overrides.
        timeout: A per-sample timeout.
        seed: The RNG seed.
        keep: Whether to keep work directories.
        python: The Python of the subject venv.
        threshold: The practical threshold in percent.
        alpha: The significance level.
        fail_on: When to exit with 2.
        fail_on_inconclusive: Whether to exit with 3 on inconclusive results.
        save: Whether to autosave the result.
        save_as: A baseline name to also store the result as.
        json_path: A file to also write the result to.
        ndjson: Whether to stream NDJSON events on stdout.
        smoke: Whether to only check that benchmarks work.
        kind: The run kind.

    Returns:
        The exit code.

    Raises:
        UsageError: On invalid options or an empty selection.
    """
    console = make_console(plain=in_ci(), stderr=ndjson)
    try:
        overrides = parse_overrides(params)
        policy = Policy(
            runs=runs,
            min_runs=min_runs,
            max_runs=max(Policy.max_runs, min_runs) if max_runs is None else max_runs,
            min_time_s=min_time,
            warmup=warmup,
            timeout_s=timeout,
            smoke=smoke,
            alpha=alpha,
            threshold_rel=threshold / 100,
            fail_on=_resolve_fail_on(fail_on),
            fail_on_inconclusive=fail_on_inconclusive,
        )
        if save_as is not None:
            check_baseline_name(save_as)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    benchmarks = _select(filters, suite, overrides)

    home = bench_home()
    subject = _resolve(reflex, python, home, console)
    seed = secrets.randbits(32) if seed is None else seed
    doc = _new_doc(subject, policy, seed, ctx.meta.get(_ARGV, []), kind)
    # Resolve the baseline before running, so a typo does not waste a whole run.
    base_doc = None
    if baseline is not None:
        try:
            base_doc = load(
                resolve_baseline(baseline, doc["machine"]["profile_id"], home)
            )
        except (FileNotFoundError, SchemaError) as exc:
            raise click.UsageError(str(exc)) from exc
    render_header(console, doc, warning_count(doc["machine"]))

    started = time.perf_counter()
    live = console.is_terminal and not in_ci()
    with _Progress(console, live=live, ndjson=ndjson) as progress:
        scheduler = Scheduler(
            subject, policy, home=home, seed=seed, keep=keep, on_event=progress.emit
        )
        try:
            scheduler.run(plan(benchmarks, overrides, suite))
        except KeyboardInterrupt:
            # The instance in progress has no complete entry, so it is left out.
            doc["interrupted"] = True
    doc["benchmarks"] = scheduler.finished
    doc["invocation"]["duration_s"] = round(time.perf_counter() - started, 3)
    if not live:
        console.print()
    render_run(console, doc)

    if baseline is not None and base_doc is not None:
        comparing.compare(
            base_doc,
            doc,
            threshold=policy.threshold_rel,
            alpha=policy.alpha,
            confidence=policy.confidence,
            resamples=policy.bootstrap_resamples,
            seed=seed,
            base_label=baseline,
            head_label="this run",
        )
        console.print()
        render_comparison(console, doc)
    return _finish(
        console,
        doc,
        home,
        save=save,
        save_as=save_as,
        json_path=json_path,
        ndjson=ndjson,
        kept=scheduler.kept,
        compared=base_doc is not None,
    )


@cli.command("ab")
@click.argument("filters", nargs=-1)
@click.option("--suite", type=click.Choice(SUITES), help="A named selection.")
@click.option(
    "--base",
    metavar="SPEC",
    callback=_check_spec,
    help="The reference subject, arm A: workspace, a PyPI version, git:<ref> or path:<dir>.",
)
@click.option(
    "--head",
    metavar="SPEC",
    required=True,
    callback=_check_spec,
    help="The subject judged against --base, arm B.",
)
@click.option(
    "--aa",
    is_flag=True,
    help="A/A control: measure --head in both arms (no --base) to see the noise floor.",
)
@click.option(
    "--rounds",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Timed samples per arm; there is no automatic run count.",
)
@click.option(
    "--warmup",
    type=click.IntRange(min=0),
    help="Untimed samples per arm. Default: per benchmark.",
)
@click.option(
    "--order",
    type=click.Choice(ab.ORDERS),
    default="abba",
    show_default=True,
    help="The arms' order in each round: AB, BA, AB, ... or a seeded coin flip.",
)
@_instance_options
@_stats_options
@_fail_options
@_output_options
@click.pass_context
def ab_command(
    ctx: click.Context,
    filters: tuple[str, ...],
    suite: str | None,
    base: str | None,
    head: str,
    aa: bool,
    rounds: int,
    warmup: int | None,
    order: ab.Order,
    params: tuple[str, ...],
    timeout: float | None,
    seed: int | None,
    keep: bool,
    python: str,
    threshold: float,
    alpha: float,
    fail_on: FailOn | None,
    fail_on_inconclusive: bool,
    save: bool,
    save_as: str | None,
    json_path: Path | None,
    ndjson: bool,
) -> int:
    """Compare two subjects on this machine, alternating their samples.

    Both subjects' sessions of a benchmark are open at once and the timed
    samples alternate (AB, BA, AB, ...), so machine drift hits both arms alike;
    then arm B (--head) is compared with arm A (--base). FILTERS are globs on
    the benchmark id, e.g. 'lifecycle.*'.

    Args:
        ctx: The click context.
        filters: Globs on the benchmark id.
        suite: A named selection.
        base: The spec of arm A.
        head: The spec of arm B.
        aa: Whether to measure ``head`` in both arms.
        rounds: Timed samples per arm.
        warmup: Untimed samples per arm.
        order: The order of the arms within each round.
        params: ``KEY=VALUE`` parameter overrides.
        timeout: A per-sample timeout.
        seed: The RNG seed.
        keep: Whether to keep work directories.
        python: The Python of subject venvs.
        threshold: The practical threshold in percent.
        alpha: The significance level.
        fail_on: When to exit with 2.
        fail_on_inconclusive: Whether to exit with 3 on inconclusive results.
        save: Whether to autosave the result.
        save_as: A baseline name to also store the result as.
        json_path: A file to also write the result to.
        ndjson: Whether to stream NDJSON events on stdout.

    Returns:
        The exit code.

    Raises:
        UsageError: On invalid options or an empty selection.
    """
    console = make_console(plain=in_ci(), stderr=ndjson)
    if aa and base is not None:
        msg = "--aa takes --head only: it measures that subject in both arms"
        raise click.UsageError(msg)
    if not aa and base is None:
        msg = "--base is required unless --aa is given"
        raise click.UsageError(msg)
    try:
        overrides = parse_overrides(params)
        policy = Policy(
            runs=rounds,
            warmup=warmup,
            timeout_s=timeout,
            alpha=alpha,
            threshold_rel=threshold / 100,
            fail_on=_resolve_fail_on(fail_on),
            fail_on_inconclusive=fail_on_inconclusive,
        )
        if save_as is not None:
            check_baseline_name(save_as)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    benchmarks = _select(filters, suite, overrides)

    home = bench_home()
    # Both environments are built before anything is timed.
    if base is None:
        base_subject = head_subject = _resolve(head, python, home, console)
    else:
        base_subject = _resolve(base, python, home, console)
        head_subject = _resolve(head, python, home, console)
    # The workspace runs on the harness's Python, other subjects on --python.
    pythons = [
        ".".join(subject.python_version.split(".")[:2])
        for subject in (base_subject, head_subject)
    ]
    if pythons[0] != pythons[1]:
        console.print(
            Text(
                f"{WARN} arm A runs Python {pythons[0]} and arm B Python {pythons[1]}:"
                " the comparison includes that difference (match them with --python,"
                " or use path:<checkout> instead of workspace)",
                style="yellow",
            )
        )
    seed = secrets.randbits(32) if seed is None else seed
    doc = _new_doc(
        base_subject, policy, seed, ctx.meta.get(_ARGV, []), "aa" if aa else None
    )
    doc["subjects"]["B"] = head_subject.to_doc()
    render_header(console, doc, warning_count(doc["machine"]))

    started = time.perf_counter()
    live = console.is_terminal and not in_ci()
    # The --aa arms share one scheduler, so their shared cache directory is set up once.
    schedulers = [
        Scheduler(subject, policy, home=home, seed=seed, keep=keep)
        for subject in ((head_subject,) if aa else (base_subject, head_subject))
    ]
    with _Progress(console, live=live, ndjson=ndjson) as progress:
        doc["benchmarks"] = ab.run(
            plan(benchmarks, overrides, suite),
            schedulers[0],
            schedulers[-1],
            order=order,
            on_event=progress.emit,
        )
    doc["invocation"]["duration_s"] = round(time.perf_counter() - started, 3)
    if not live:
        console.print()
    render_run(console, doc)
    comparing.compare(
        doc,
        doc,
        threshold=policy.threshold_rel,
        alpha=policy.alpha,
        confidence=policy.confidence,
        resamples=policy.bootstrap_resamples,
        seed=seed,
        base_label=f"A={base_subject.spec}",
        head_label=f"B={head_subject.spec}",
        base_arm="A",
        head_arm="B",
    )
    console.print()
    render_comparison(console, doc)
    return _finish(
        console,
        doc,
        home,
        save=save,
        save_as=save_as,
        json_path=json_path,
        ndjson=ndjson,
        kept=[path for scheduler in schedulers for path in scheduler.kept],
        compared=True,
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--samples", is_flag=True, help="Also print every raw sample.")
def show(path: Path, samples: bool) -> int:
    """Show one result in detail.

    Args:
        path: The result JSON file.
        samples: Whether to print every raw sample.

    Returns:
        The exit code.
    """
    doc = _load(path)
    console = make_console(plain=in_ci())
    render_header(console, doc, warning_count(doc["machine"]))
    render_run(console, doc)
    if doc.get("compared_to"):
        console.print()
        render_comparison(console, doc)
    if samples:
        console.print()
        render_samples(console, doc)
    return EXIT_OK


def _load(path: Path) -> ResultDoc:
    """Load a result, turning schema errors into usage errors.

    Args:
        path: The result JSON file.

    Returns:
        The document.

    Raises:
        UsageError: When the file is not a valid result.
    """
    try:
        return load(path)
    except SchemaError as exc:
        raise click.UsageError(str(exc)) from exc


@cli.command("compare")
@click.argument("base", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("head", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["term", "md", "json"]),
    default="term",
    show_default=True,
)
@_stats_options
@click.option("--force", is_flag=True, help="Compare entries whose series keys differ.")
@_fail_options
def compare_command(
    base: Path,
    head: Path,
    output_format: str,
    threshold: float,
    alpha: float,
    force: bool,
    fail_on: FailOn | None,
    fail_on_inconclusive: bool,
) -> int:
    """Compare two results (BASE is the reference).

    Args:
        base: The baseline result file.
        head: The result file to judge.
        output_format: ``term``, ``md`` or ``json`` (the annotated head result).
        threshold: The practical threshold in percent.
        alpha: The significance level.
        force: Whether to compare entries with different series keys.
        fail_on: When to exit with 2.
        fail_on_inconclusive: Whether to exit with 3 on inconclusive results.

    Returns:
        The exit code.
    """
    base_doc, head_doc = _load(base), _load(head)
    comparing.compare(
        base_doc,
        head_doc,
        threshold=threshold / 100,
        alpha=alpha,
        confidence=head_doc["policy"]["confidence"],
        resamples=head_doc["policy"]["bootstrap_resamples"],
        seed=head_doc["invocation"]["rng_seed"],
        force=force,
        base_label=str(base),
        head_label=str(head),
    )
    if output_format == "md":
        click.echo(markdown_comparison(head_doc), nl=False)
    elif output_format == "json":
        click.echo(dumps(head_doc), nl=False)
    else:
        render_comparison(make_console(plain=in_ci()), head_doc)
    return _exit_code(
        head_doc, _resolve_fail_on(fail_on), fail_on_inconclusive, compared=True
    )


@cli.command()
def doctor() -> int:
    """Check the machine for settings that make measurements noisy.

    Returns:
        The exit code (always 0: warnings never block a run).
    """
    machine = collect()
    console = make_console(plain=in_ci())
    scopes, scope_status = cgroup.status()
    found = [
        *checks(machine),
        Check(
            "cgroup scope",
            "ok" if scopes else "info",
            scope_status,
            None if scopes else "peak memory falls back to PSS sampling",
        ),
    ]
    width = max(len(check.name) for check in found)
    for check in found:
        hint = f": {check.hint}" if check.hint else ""
        style = {"warn": "yellow", "ok": "green"}.get(check.status, "")
        console.print(
            Text(
                f"{_CHECK_ICONS[check.status]} {check.name.ljust(width)}  {check.value}{hint}",
                style=style,
            )
        )
    warnings = sum(check.status == "warn" for check in found)
    console.print()
    console.print(Text(f"profile: {machine['profile_id']}"))
    console.print(
        Text(
            f"{warnings} warning{'s' if warnings != 1 else ''}"
            + (": expect extra variance; local runs still proceed" if warnings else ""),
        )
    )
    return EXIT_OK


@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--to", "target", type=click.Choice(["md", "bmf"]), required=True)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write here instead of stdout.",
)
def export(path: Path, target: str, output: Path | None) -> int:
    """Export a result as pull request markdown or Bencher Metric Format.

    Args:
        path: The result JSON file.
        target: ``md`` or ``bmf``.
        output: A file to write instead of standard output.

    Returns:
        The exit code.
    """
    doc = _load(path)
    text = (
        markdown_comparison(doc)
        if target == "md"
        else json.dumps(to_bmf(doc), indent=2, allow_nan=False) + "\n"
    )
    if output is None:
        click.echo(text, nl=False)
    else:
        output.write_text(text, encoding="utf-8")
    return EXIT_OK


@cli.group("subjects")
def subjects_command() -> None:
    """Manage the cached virtualenvs of --reflex, --base and --head subjects."""


@subjects_command.command("list")
def subjects_list() -> int:
    """List the cached subject venvs: spec, Python, key, size and last use.

    Returns:
        The exit code.
    """
    console = make_console(plain=in_ci())
    home = bench_home()
    venvs = subjects.cached_venvs(home)
    if not venvs:
        console.print(Text(f"no cached subject venvs in {_relative(home / 'venvs')}"))
        return EXIT_OK
    sizes = [venv.size() for venv in venvs]
    rows = [["spec", "python", "key", "size", "last used"]]
    rows.extend(
        [
            venv.spec,
            venv.python,
            venv.key,
            format_value(size, "B"),
            datetime.fromtimestamp(venv.last_used).strftime("%Y-%m-%d %H:%M"),
        ]
        for venv, size in zip(venvs, sizes, strict=True)
    )
    _print_rows(console, rows)
    plural = "" if len(venvs) == 1 else "s"
    console.print(
        Text(f"{len(venvs)} venv{plural} {DOT} {format_value(sum(sizes), 'B')}")
    )
    return EXIT_OK


def _parse_age(ctx: click.Context, param: click.Parameter, value: str) -> timedelta:
    """Parse an age such as ``30d``, ``12h`` or ``90m``.

    Args:
        ctx: The click context.
        param: The option.
        value: The age.

    Returns:
        The age.

    Raises:
        BadParameter: When it is not a whole number of days, hours or minutes.
    """
    match = _AGE.fullmatch(value)
    if match is None:
        msg = f"expected a number of days, hours or minutes such as 30d, 12h or 90m, got {value!r}"
        raise click.BadParameter(msg)
    return timedelta(**{_AGE_UNITS[match[2]]: int(match[1])})


@subjects_command.command("prune")
@click.option(
    "--older-than",
    default="30d",
    show_default=True,
    metavar="AGE",
    callback=_parse_age,
    help="Delete venvs not used for this long (30d, 12h, 90m).",
)
def subjects_prune(older_than: timedelta) -> int:
    """Delete subject venvs not used for a while.

    Also deletes the leftovers of interrupted builds and the git worktrees that
    no remaining venv is installed from.

    Args:
        older_than: How long a venv must have gone unused.

    Returns:
        The exit code.
    """
    console = make_console(plain=in_ci())
    removed = subjects.prune(
        bench_home(), older_than, echo=lambda message: console.print(Text(message))
    )
    if not removed:
        console.print(Text("nothing to prune"))
    return EXIT_OK


cli.add_command(budgets_command)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the ``reflex-bench`` command.

    Args:
        argv: The arguments; defaults to ``sys.argv[1:]``.
    """
    for stream in (sys.stdout, sys.stderr):
        # A console without UTF-8 must not crash on the report's symbols.
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    cli.main(args=None if argv is None else list(argv), prog_name="reflex-bench")
