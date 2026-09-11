"""Offline: which components emit a `package_path` subpath import inside a dynamic component."""

import reflex

assert "/envs/" in reflex.__file__, reflex.__file__
print("reflex:", reflex.constants.Reflex.VERSION, reflex.__file__)

import reflex as rx
from reflex_base.utils.serializers import serialize


def show(label, comp):
    """Print the import lines of the serialized dynamic module."""
    try:
        code = str(serialize(comp))
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: ERROR {type(exc).__name__}: {exc}")
        return
    print(f"\n--- {label} ---")
    for line in code.splitlines():
        if line.startswith("import ") or "window.__reflex[" in line:
            print("   ", line)


show("rx.icon('apple')", rx.vstack(rx.icon("apple")))

try:
    import plotly.graph_objects as go

    fig = go.Figure(data=[go.Bar(x=[1], y=[2])])
    show("rx.plotly(data=fig)", rx.vstack(rx.plotly(data=fig)))
except ImportError as exc:
    print("plotly not installed:", exc)

try:
    import reflex_enterprise as rxe

    show(
        "rxe.highcharts.chart (package_path='/')",
        rx.vstack(rxe.highcharts.chart(options={})),
    )
except Exception as exc:  # noqa: BLE001
    print("enterprise probe skipped:", type(exc).__name__, exc)
