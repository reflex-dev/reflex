"""Benchmarks for building var operations.

Every derived Var — arithmetic, comparisons, boolean logic, string/array/object
methods, iteration, ``rx.cond`` — is built by a ``@var_operation``, which
interpolates each operand into the JavaScript expression it returns. That
interpolation runs ``Var.__format__``, which hashes the operand (recursively
hashing its ``VarData``), stores it in a module-global registry, and emits a
marker tag that the constructed Var then decodes back out with a regex.

Evaluating and compiling a page builds these by the thousand, but the page
benchmarks are dominated by component construction, so a change to the operand
path barely registers there. These benchmarks isolate it.

Each benchmark builds one family of operations, flat, over operands built
outside the measured body: an operation whose operand is itself a freshly built
operation costs more than one over a plain var, and mixing the two in a single
benchmark makes it impossible to tell which moved. ``test_chained_operations``
owns that second dimension on its own, and ``test_evaluate_var_heavy_page`` is
where the families appear mixed the way real code writes them.

Some operations stand alone rather than joining a family, because they are
built without interpolating an operand at all and would be too small a share of
one to read: string concatenation, array indexing, array ranges, and
``rx.match``.

Operands are parametrized by whether they carry ``VarData`` at all, because
that is what the interpolation cost turns on: a bare Var carries none, while a
state var carries its state name, field name, context imports, hook and app
wraps. A var carrying even more of it measures the same, since ``VarData``
caches its own hash and these benchmarks reuse one operand — a fresh operand
per level is what ``test_chained_operations`` covers.
"""

import datetime
import operator
from collections.abc import Callable
from typing import cast

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component
from reflex_base.vars.base import Var
from reflex_base.vars.datetime import DateTimeVar
from reflex_base.vars.number import NumberVar
from reflex_base.vars.sequence import ArrayVar

import reflex as rx
from reflex.state import BaseState

# How many times each benchmark repeats the set of operations it names. The
# counts differ because the sets do: each is tuned so every body builds roughly
# two milliseconds' worth of operations uninstrumented. Keeping every body
# comparable, and none of them near-trivial, is what stops the fixed cost of
# entering the measured call from dominating a benchmark — a body small enough
# for that reports changes it never exercised, which read as regressions.
# Retune from the wall-clock table that
# ``uv run pytest tests/benchmarks/test_var_operations.py`` prints if the cost
# of an operation changes materially.
ARITHMETIC_SETS = 27
COMPARISON_SETS = 22
BOOLEAN_SETS = 17
STRING_SETS = 13
CONCAT_SETS = 39
ARRAY_SETS = 19
INDEX_SETS = 170
RANGE_SETS = 65
OBJECT_SETS = 28
ITERATION_SETS = 4
DATETIME_SETS = 17
CAST_SETS = 48
MATCH_SETS = 71
COND_SETS = 44
FORMAT_SETS = 515

# Operations built by every depth of the chained-operation benchmark. Holding
# the total fixed rather than the repeat count keeps the depths comparable to
# each other: they differ only in how deeply the operations nest, not in how
# many get built. Every entry of DEPTHS must divide it.
CHAIN_OPERATIONS = 64
DEPTHS = (2, 8, 32)

# Rows in the end-to-end page. It is the one benchmark deliberately larger than
# the rest, in line with the other page benchmarks in this suite.
PAGE_ROWS = 25


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

    numbers: rx.Field[list[int]] = rx.field(default_factory=list)

    meta: rx.Field[dict[str, int]] = rx.field(default_factory=dict)

    extra: rx.Field[dict[str, int]] = rx.field(default_factory=dict)

    when: rx.Field[datetime.datetime] = rx.field(datetime.datetime(2024, 1, 1))

    day: rx.Field[datetime.date] = rx.field(datetime.date(2024, 1, 1))


# The right-hand sides of the datetime comparisons, built once so the benchmark
# measures the operation and not the literal.
_OTHER_DATETIME = datetime.datetime(2025, 6, 1)
_OTHER_DATE = datetime.date(2025, 6, 1)

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
        for i in range(ARITHMETIC_SETS):
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
        for i in range(COMPARISON_SETS):
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
        for _i in range(BOOLEAN_SETS):
            _ = enabled & verbose
            _ = enabled | verbose
            _ = ~enabled


@pytest.mark.parametrize("depth", DEPTHS)
def test_chained_operations(depth: int, benchmark: BenchmarkFixture):
    """Benchmark chaining operations, where each operand is the previous result.

    Every level interpolates a freshly built operand whose expression and merged
    VarData are both new, so nothing the operand path computes can be reused.
    This is the only benchmark here that nests; the rest stay flat so the two
    effects can be read apart. Each depth builds the same number of operations,
    so the three differ only in how deeply they nest.

    Args:
        depth: How many operations to chain.
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count
    chains = CHAIN_OPERATIONS // depth

    @benchmark
    def _():
        for _c in range(chains):
            accumulated = count
            for i in range(depth):
                accumulated = accumulated + i


def test_string_operations(benchmark: BenchmarkFixture):
    """Benchmark building string operations over a state var.

    Concatenation has its own benchmark; see ``test_string_concat_operation``.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    label = VarOpState.label

    @benchmark
    def _():
        for _i in range(STRING_SETS):
            _ = label.lower()
            _ = label.upper()
            _ = label.strip()
            _ = label.split(",")
            _ = label.contains("a")
            _ = label.startswith("b")
            _ = label.replace("c", "d")


def test_string_concat_operation(benchmark: BenchmarkFixture):
    """Benchmark building string concatenation, expression included.

    Kept apart from the other string operations because it is built
    differently: ``+`` builds a ``ConcatVarOperation``, which assembles its
    expression with ``str()`` and never interpolates an operand the way the
    rest of the family does. Folded in there it would be a few percent of the
    body, too little for a change to it to be readable.

    This is the one benchmark that renders what it builds. The rest interpolate
    their operands while the operation is constructed, so building is the work;
    a concat defers its whole assembly to ``_cached_var_name``, and measured
    without ``str()`` it reports only the allocation — around 40% of its cost.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    label = VarOpState.label
    fallback = VarOpState.fallback

    @benchmark
    def _():
        for _i in range(CONCAT_SETS):
            _ = str(label + fallback)
            _ = str(label + " items")
            _ = str(label + " / " + fallback + "!")


def test_array_operations(benchmark: BenchmarkFixture):
    """Benchmark building array operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    tags = VarOpState.tags

    @benchmark
    def _():
        for _i in range(ARRAY_SETS):
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
        for i in range(INDEX_SETS):
            _ = tags[i]


def test_array_range_operation(benchmark: BenchmarkFixture):
    """Benchmark building ``ArrayVar.range``, which backs a counted foreach.

    The sibling of ``test_array_index_operation``: ``array_range_operation`` is
    the other ``@var_operation`` rendering its operands with ``!s``, so it is
    built without interpolating one either.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count

    @benchmark
    def _():
        for _i in range(RANGE_SETS):
            _ = ArrayVar.range(count)
            _ = ArrayVar.range(0, count, 2)


def test_iteration_operations(benchmark: BenchmarkFixture):
    """Benchmark building the array iteration operations behind ``rx.foreach``.

    Each of these traces the Python callable it is given into an
    ``ArgsFunctionOperation`` before building the operation itself, which makes
    them the most expensive family here per operation built.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    numbers = VarOpState.numbers
    tags = VarOpState.tags

    @benchmark
    def _():
        for _i in range(ITERATION_SETS):
            _ = numbers.map(lambda value: value + 1)
            _ = numbers.filter(lambda value: value > 1)
            _ = numbers.reduce(operator.add, 0)
            _ = tags.flat_map(lambda tag: tag.split(","))


def test_object_operations(benchmark: BenchmarkFixture):
    """Benchmark building object operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    meta = VarOpState.meta
    extra = VarOpState.extra

    @benchmark
    def _():
        for _i in range(OBJECT_SETS):
            _ = meta.keys()
            _ = meta.values()
            _ = meta.entries()
            _ = meta.merge(extra)


def test_datetime_operations(benchmark: BenchmarkFixture):
    """Benchmark building datetime and date comparisons.

    Both operands go into a ``compareDatetime`` call, so these are two-operand
    interpolations like the boolean ones.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    # Cast: the Field descriptor is typed Var[datetime], while the operations
    # under test are declared on DateTimeVar, which is what it really returns.
    when = cast(DateTimeVar, VarOpState.when)
    day = cast(DateTimeVar, VarOpState.day)

    @benchmark
    def _():
        for _i in range(DATETIME_SETS):
            _ = when > _OTHER_DATETIME
            _ = when == _OTHER_DATETIME
            _ = day <= _OTHER_DATE


def test_cast_operations(benchmark: BenchmarkFixture):
    """Benchmark building the casts that wrap a var for display or a condition.

    ``rx.text(State.count)`` and every truthiness check go through these.
    ``bool()`` interpolates its operand into an ``isTrue`` call, while
    ``to_string`` and ``to`` build through a function call and a ToOperation
    instead, so this benchmark covers both shapes.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count

    @benchmark
    def _():
        for _i in range(CAST_SETS):
            _ = count.to_string()
            _ = count.to(str)
            _ = count.bool()


def test_match_operation(benchmark: BenchmarkFixture):
    """Benchmark building an ``rx.match`` switch over a state var.

    A switch is built from its cases rather than by interpolating operands, so
    it stands alone rather than joining the comparison family it resembles.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    label = VarOpState.label

    @benchmark
    def _():
        for _i in range(MATCH_SETS):
            _ = rx.match(label, ("a", 1), ("b", 2), ("c", 3), 0)


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
        for _i in range(COND_SETS):
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
        for i in range(FORMAT_SETS):
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

    return rx.vstack(*(row(i) for i in range(PAGE_ROWS)))


def test_evaluate_var_heavy_page(benchmark: BenchmarkFixture):
    """Benchmark evaluating a page built out of var operations.

    The existing page benchmarks spend most of their time constructing
    components; this one spends it building the vars those components hold.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(_var_heavy_page)
def test_var_arithmetic_chain(benchmark: BenchmarkFixture):
    """Benchmark construction of a representative arithmetic expression.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    left = Var.create(1)
    right = Var.create(2)
    result = benchmark(lambda: ((left + right) * right - left) / right)
    assert result._js_expr


def test_var_to_dispatch(benchmark: BenchmarkFixture):
    """Benchmark conversion through the Var subclass registry.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    value = Var(_js_expr="value", _var_type=int)
    result = benchmark(lambda: value.to(float))
    assert result._var_type is float


def test_var_guess_type_dispatch(benchmark: BenchmarkFixture):
    """Benchmark inferred dispatch through the Var subclass registry.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    value = Var(_js_expr="value", _var_type=list[int])
    result = benchmark(value.guess_type)
    assert result._var_type == list[int]
