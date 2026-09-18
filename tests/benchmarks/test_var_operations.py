"""Benchmarks for building var operations.

Every derived Var — arithmetic, comparisons, string/array/object methods,
``rx.cond`` — is built by a ``@var_operation``, which interpolates each operand
into the JavaScript expression it returns. That interpolation runs
``Var.__format__``, which hashes the operand (recursively hashing its
``VarData``), stores it in a module-global registry, and emits a marker tag that
the constructed Var then decodes back out with a regex.

Evaluating and compiling a page builds these by the thousand, but the page
benchmarks are dominated by component construction, so a change to the operand
path barely registers there. These benchmarks isolate it.

Operands are parametrized by how much ``VarData`` they carry, because that is
what the interpolation cost scales with: a bare Var carries none, a state var
carries its state and field name, and a component-provided var carries imports
and hooks.
"""

from collections.abc import Callable

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.number import NumberVar

import reflex as rx

# Expressions built per benchmark iteration. Large enough that the operand
# path dominates the fixture and call overhead, small enough to stay cheap
# under the CodSpeed simulation instrument.
N = 25

# Nesting depths for the chained-operation benchmark. Each level re-interpolates
# the level below, whose expression and merged VarData are both freshly built,
# so the operand path costs more the deeper an expression gets.
DEPTHS = (2, 8, 32)


class VarOpState(rx.State):
    """State supplying operands that carry a state name and field name."""

    count: rx.Field[int] = rx.field(0)

    label: rx.Field[str] = rx.field("")

    tags: rx.Field[list[str]] = rx.field(default_factory=list)

    meta: rx.Field[dict[str, int]] = rx.field(default_factory=dict)


# A var as a component hands one out: imports and hooks to merge, which is the
# bulk of what hashing an operand walks.
_COMPONENT_VAR_DATA = VarData(
    imports={
        "react": [ImportVar(tag="useCallback"), ImportVar(tag="useState")],
        "/utils/state": [ImportVar(tag="getBackendURL")],
    },
    hooks={
        "const [value, setValue] = useState(null)": None,
        "const refresh = useCallback(() => setValue(null), [])": None,
    },
)

_NUMBER_OPERANDS: dict[str, Callable[[], NumberVar[int]]] = {
    # A bare Var with no VarData: the cheapest operand to interpolate.
    "bare": lambda: Var(_js_expr="bare_value").to(int),
    "state": lambda: VarOpState.count,
    "component": lambda: Var(
        _js_expr="component_value", _var_data=_COMPONENT_VAR_DATA
    ).to(int),
}


@pytest.fixture(params=list(_NUMBER_OPERANDS), scope="module")
def number_operand(request: pytest.FixtureRequest) -> NumberVar[int]:
    """A number operand, parametrized by how much VarData it carries.

    Args:
        request: The fixture request holding the operand name.

    Returns:
        The number var to build operations from.
    """
    return _NUMBER_OPERANDS[request.param]()


def test_arithmetic_operations(
    number_operand: NumberVar[int], benchmark: BenchmarkFixture
):
    """Benchmark building arithmetic operations over a single operand.

    Args:
        number_operand: The number var to build operations from.
        benchmark: The codspeed benchmark fixture.
    """
    count = number_operand

    @benchmark
    def _():
        for i in range(N):
            _ = (count + i) * 2 - count / (i + 1)


def test_comparison_operations(
    number_operand: NumberVar[int], benchmark: BenchmarkFixture
):
    """Benchmark building comparison and boolean operations over one operand.

    Args:
        number_operand: The number var to build operations from.
        benchmark: The codspeed benchmark fixture.
    """
    count = number_operand

    @benchmark
    def _():
        for i in range(N):
            _ = (count > i) & (count < i * 2) | (count == i)


@pytest.mark.parametrize("depth", DEPTHS)
def test_chained_operations(depth: int, benchmark: BenchmarkFixture):
    """Benchmark chaining operations, where each operand is the previous result.

    Every level interpolates a freshly built operand whose expression and merged
    VarData are both new, so nothing the operand path computes can be reused.

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

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    label = VarOpState.label

    @benchmark
    def _():
        for i in range(N):
            _ = label.lower().strip().split(",")
            _ = label.contains(str(i)) & label.startswith("a")
            _ = label + str(i)


def test_array_operations(benchmark: BenchmarkFixture):
    """Benchmark building array operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    tags = VarOpState.tags

    @benchmark
    def _():
        for i in range(N):
            _ = tags.reverse().join(", ")
            _ = tags.length() > i
            _ = tags[i].upper()


def test_object_operations(benchmark: BenchmarkFixture):
    """Benchmark building object operations over a state var.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    meta = VarOpState.meta

    @benchmark
    def _():
        for i in range(N):
            _ = meta.keys().join(",")
            _ = meta.values().length() + i
            _ = meta.entries().length()


def test_cond_operations(benchmark: BenchmarkFixture):
    """Benchmark building ``rx.cond`` ternaries over state vars.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    count = VarOpState.count
    label = VarOpState.label

    @benchmark
    def _():
        for i in range(N):
            _ = rx.cond(count > i, label.upper(), label.lower())


def test_format_var_outside_operation(benchmark: BenchmarkFixture):
    """Benchmark interpolating a var outside any operation.

    User code writes ``f"Count: {State.count}"`` directly, which tags the var so
    its VarData survives into the surrounding string. This path is deliberately
    unchanged by operand handling inside ``var_operation``; the benchmark guards
    it against regressing.

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
    constructing components.

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
