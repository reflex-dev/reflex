"""Ten memo bodies, each deriving 200 conditional Vars at compile time."""

import reflex as rx
from .model import Workload


@rx.memo
def panel_0(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 0 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-0",
        class_name="compile-panel",
    )


@rx.memo
def panel_1(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 1 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-1",
        class_name="compile-panel",
    )


@rx.memo
def panel_2(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 2 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-2",
        class_name="compile-panel",
    )


@rx.memo
def panel_3(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 3 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-3",
        class_name="compile-panel",
    )


@rx.memo
def panel_4(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 4 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-4",
        class_name="compile-panel",
    )


@rx.memo
def panel_5(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 5 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-5",
        class_name="compile-panel",
    )


@rx.memo
def panel_6(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 6 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-6",
        class_name="compile-panel",
    )


@rx.memo
def panel_7(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 7 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-7",
        class_name="compile-panel",
    )


@rx.memo
def panel_8(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 8 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-8",
        class_name="compile-panel",
    )


@rx.memo
def panel_9(seed: rx.Var[int], labels: rx.Var[list[int]]) -> rx.Component:
    """Build memo panel 9 with 200 derived Vars and a 200-item foreach.

    Args:
        seed: Dynamic arithmetic input.
        labels: The foreach input list.

    Returns:
        Compilable condition/arithmetic expressions in an ordinary component.
    """
    expressions = [
        rx.cond(
            (seed + offset) % 3 == 0,
            (seed + offset) * (offset + 1),
            (seed - offset) * (offset + 2),
        )
        for offset in range(200)
    ]
    return rx.el.div(
        rx.el.div(
            rx.foreach(
                labels,
                lambda value: rx.el.span(
                    rx.cond(value % 2 == 0, value + seed, value * seed)
                ),
            ),
            class_name="foreach-values",
        ),
        rx.el.div(
            *[rx.el.span(value) for value in expressions],
            class_name="expression-values",
        ),
        id="panel-9",
        class_name="compile-panel",
    )


def compile_page() -> rx.Component:
    """Build the dedicated compile workload route.

    Returns:
        Ten distinct memo bodies totaling exactly 2,000 conditional Var results.
    """
    return rx.el.div(
        "Compile workload: 2000 derived Vars",
        panel_0(seed=Workload.seed, labels=Workload.labels),
        panel_1(seed=Workload.seed, labels=Workload.labels),
        panel_2(seed=Workload.seed, labels=Workload.labels),
        panel_3(seed=Workload.seed, labels=Workload.labels),
        panel_4(seed=Workload.seed, labels=Workload.labels),
        panel_5(seed=Workload.seed, labels=Workload.labels),
        panel_6(seed=Workload.seed, labels=Workload.labels),
        panel_7(seed=Workload.seed, labels=Workload.labels),
        panel_8(seed=Workload.seed, labels=Workload.labels),
        panel_9(seed=Workload.seed, labels=Workload.labels),
    )
