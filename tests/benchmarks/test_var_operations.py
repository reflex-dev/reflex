"""Benchmarks for building var operations.

Every derived Var — arithmetic, comparisons, boolean logic, string/array/object
methods, ``rx.cond`` — is built by a ``@var_operation``, which interpolates each
operand into the JavaScript expression it returns. That interpolation runs
``Var.__format__``, which hashes the operand (recursively hashing its
``VarData``), stores it in a module-global registry, and emits a marker tag that
the constructed Var then decodes back out with a regex.

Evaluating and compiling a page builds these by the thousand, but the page
benchmarks are dominated by component construction, so a change to the operand
path barely registers there. These benchmarks isolate it.

Each benchmark builds one family of operations, flat, over operands built
outside the measured body: an operation whose operand is itself a freshly built
operation costs more than one over a plain var, and mixing the two in a single
benchmark makes it impossible to tell which moved. ``test_chained_operations``
owns that second dimension on its own, and ``test_evaluate_var_heavy_page`` is
where the families appear mixed the way real code writes them.

Operands are parametrized by whether they carry ``VarData`` at all, because
that is what the interpolation cost turns on: a bare Var carries none, while a
state var carries its state name, field name, context imports, hook and app
wraps. A var carrying even more of it measures the same, since ``VarData``
caches its own hash and these benchmarks reuse one operand — a fresh operand
per level is what ``test_chained_operations`` covers.
"""

from collections.abc import Callable

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component
from reflex_base.vars.base import Var
from reflex_base.vars.number import NumberVar

import reflex as rx
from reflex.state import BaseState

# Expressions built per benchmark iteration. Large enough that the operand
# path dominates the fixture and call overhead, small enough to stay cheap
# under the CodSpeed simulation instrument.
N = 25

# Nesting depths for the chained-operation benchmark. Each level re-interpolates
# the level below, whose expression and merged VarData are both freshly built,
# so the operand path costs more the deeper an expression gets.
DEPTHS = (2, 8, 32)


class VarOpState(BaseState):
    """State supplying operands that carry a state name and field name.

    Subclasses ``BaseState`` directly rather than ``rx.State`` so it stays out
    of the state tree the event-processing benchmarks walk, which a substate
    registered here would otherwise make measurably bigger.
    """

    count: rx.Field[int] = rx.field(0)

    enabled: rx.Field[bool] = rx.field(False)

    verbose: rx.Field[bool] = rx.field(False)

    label: rx.Field[str] = rx.field("")

    fallback: rx.Field[str] = rx.field("")

    tags: rx.Field[list[str]] = rx.field(default_factory=list)

    meta: rx.Field[dict[str, int]] = rx.field(default_factory=dict)

    extra: rx.Field[dict[str, int]] = rx.field(default_factory=dict)


_NUMBER_OPERANDS: dict[str, Callable[[], NumberVar[int]]] = {
    # A bare Var with no VarData: the cheapest operand to interpolate.
    "bare": lambda: Var(_js_expr="bare_value").to(int),
    "state": lambda: VarOpState.count,
}


@pytest.fixture(params=list(_NUMBER_OPERANDS), scope="module")
def number_operand(request: pytest.FixtureRequest) -> NumberVar[int]:
    """A number operand, parametrized by whether it carries VarData.

    Args:
        request: The fixture request holding the operand name.

    Returns:
        The number var to build operations from.
    """
    return _NUMBER_OPERANDS[request.param]()


def test_arithmetic_operations(
    number_operand: NumberVar[int], benchmark: BenchmarkFixture
):
    """Benchmark building arithmetic operations directly over one operand.

    Args:
        number_operand: The number var to build operations from.
        benchmark: The codspeed benchmark fixture.
    """
    count = number_operand

    @benchmark
    def _():
        for i in range(N):
            _ = count + i
            _ = count - i
            _ = count * i
            _ = count / (i + 1)


def test_comparison_operations(
    number_operand: NumberVar[int], benchmark: BenchmarkFixture
):
    """Benchmark building comparison operations directly over one operand.

    Args:
        number_operand: The number var to build operations from.
        benchmark: The codspeed benchmark fixture.
    """
    count = number_operand

    @benchmark
    def _():
        for i in range(N):
            _ = count > i
            _ = count < i
            _ = count >= i
            _ = count == i
            _ = count != i


def test_boolean_operations(benchmark: BenchmarkFixture):
    """Benchmark building boolean operations over state vars.

    ``&`` and ``|`` interpolate both operands into a ``pyAnd``/``pyOr`` call and
    carry their own imports, so they are the widest of the two-operand cases.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    enabled = VarOpState.enabled
    verbose = VarOpState.verbose

    @benchmark
    def _():
        for _i in range(N):
            _ = enabled & verbose
            _ = enabled | verbose
            _ = ~enabled


@pytest.mark.parametrize("depth", DEPTHS)
def test_chained_operations(depth: int, benchmark: BenchmarkFixture):
    """Benchmark chaining operations, where each operand is the previous result.

    Every level interpolates a freshly built operand whose expression and merged
    VarData are both new, so nothing the operand path computes can be reused.
    This is the only benchmark here that nests; the rest stay flat so the two
    effects can be read apart.

    Args:
        depth: How many operations to chain.
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count

    @benchmark
    def _():
        accumulated = count
        for i in range(depth):
            accumulated = accumulated + i


def test_string_operations(benchmark: BenchmarkFixture):
    """Benchmark building string operations over a state var.

    ``+`` is left out: string concatenation builds a ``ConcatVarOperation``,
    which assembles its expression with ``str()`` and never interpolates an
    operand, so it belongs to a different path than the rest of these.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    label = VarOpState.label

    @benchmark
    def _():
        for _i in range(N):
            _ = label.lower()
            _ = label.upper()
            _ = label.strip()
            _ = label.split(",")
            _ = label.contains("a")
            _ = label.startswith("b")
            _ = label.replace("c", "d")


def test_array_operations(benchmark: BenchmarkFixture):
    """Benchmark building array operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    tags = VarOpState.tags

    @benchmark
    def _():
        for _i in range(N):
            _ = tags.length()
            _ = tags.reverse()
            _ = tags.join(", ")
            _ = tags.contains("x")
            _ = tags + tags


def test_array_index_operation(benchmark: BenchmarkFixture):
    """Benchmark building array indexing, the hot operation in a foreach body.

    Kept apart from the other array operations because it is built differently:
    ``array_item_operation`` renders its operands with ``!s``, which calls
    ``str()`` rather than ``__format__``, so indexing never interpolates an
    operand the way the rest of the family does.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    tags = VarOpState.tags

    @benchmark
    def _():
        for i in range(N):
            _ = tags[i]


def test_object_operations(benchmark: BenchmarkFixture):
    """Benchmark building object operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    meta = VarOpState.meta
    extra = VarOpState.extra

    @benchmark
    def _():
        for _i in range(N):
            _ = meta.keys()
            _ = meta.values()
            _ = meta.entries()
            _ = meta.merge(extra)


def test_cond_operations(benchmark: BenchmarkFixture):
    """Benchmark building ``rx.cond`` ternaries over state vars.

    The condition and both branches are plain state vars rather than derived
    ones, so this measures the ternary and not the comparison and string
    operations a realistic condition would be built from — those are already
    benchmarked on their own.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    enabled = VarOpState.enabled
    label = VarOpState.label
    fallback = VarOpState.fallback

    @benchmark
    def _():
        for _i in range(N):
            _ = rx.cond(enabled, label, fallback)


def test_format_var_outside_operation(benchmark: BenchmarkFixture):
    """Benchmark interpolating a var outside any operation.

    User code writes ``f"Count: {State.count}"`` directly, which tags the var so
    its VarData survives into the surrounding string. Nothing about how operands
    are interpolated inside ``var_operation`` is meant to reach this path; this
    is the control that says whether it did.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count
    label = VarOpState.label

    @benchmark
    def _():
        for i in range(N):
            _ = f"{label} has {count} items at index {i}"


def _var_heavy_page() -> Component:
    """A page whose props and children are derived vars rather than literals.

    Every row builds comparisons, string and array operations, and the
    ``rx.cond`` ternaries a dashboard uses to derive what it displays, so
    evaluating it spends its time building var operations rather than
    constructing components. Unlike the benchmarks above it deliberately mixes
    the families and nests them, the way application code writes them.

    Returns:
        The page component.
    """
    count = VarOpState.count
    label = VarOpState.label
    tags = VarOpState.tags

    def row(i: int) -> Component:
        active = (count > i) & (tags.length() > i)
        return rx.hstack(
            rx.text(
                rx.cond(active, label.upper(), label.lower()),
                color=rx.cond(active, "green", "gray"),
            ),
            rx.text(tags[i].capitalize()),
            rx.text((count * i).to_string() + " / " + tags.length().to_string()),
            rx.cond(
                label.contains(str(i)),
                rx.badge(tags.reverse().join(", ")),
                rx.badge(tags.join(" | ")),
            ),
            opacity=rx.cond(active, "1", "0.5"),
        )

    return rx.vstack(*(row(i) for i in range(N)))


def test_evaluate_var_heavy_page(benchmark: BenchmarkFixture):
    """Benchmark evaluating a page built out of var operations.

    The existing page benchmarks spend most of their time constructing
    components; this one spends it building the vars those components hold.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(_var_heavy_page)
