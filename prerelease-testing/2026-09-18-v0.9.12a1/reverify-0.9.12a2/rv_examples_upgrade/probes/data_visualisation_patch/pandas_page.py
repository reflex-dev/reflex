"""Extra page added by pre-release QA: exercises the pandas serializer (#7049)
and sqlmodel relationship serialization together with State vars, rx.memo,
ComponentState, foreach/cond and a background task.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlmodel import select

import reflex as rx

from .models import Covid

DF = pd.DataFrame(
    {"zone": ["North", "South", "East", "West"], "n": [1, 2, 3, 4]},
)


class PandasState(rx.State):
    """State holding a pandas DataFrame and model rows."""

    rows: list[Covid] = []
    tick: int = 0

    @rx.var(cache=False)
    def steady(self) -> str:
        """An uncached var whose value never changes (checks #6946)."""
        return "constant"

    @rx.var
    def frame(self) -> pd.DataFrame:
        """A DataFrame derived from a State var."""
        return DF.head(2 + (self.tick % 3))

    @rx.event
    def load(self):
        """Load a few model rows from the database."""
        with rx.session() as session:
            self.rows = session.exec(select(Covid).limit(3)).all()

    @rx.event
    def bump(self):
        """Advance the tick."""
        self.tick += 1

    @rx.var
    def chart_data(self) -> list[dict]:
        """Recharts series driven by the tick (checks the recharts alpha)."""
        return [
            {"zone": z, "n": n + self.tick}
            for z, n in zip(DF["zone"].tolist(), DF["n"].tolist())
        ]

    @rx.var
    def figure(self) -> go.Figure:
        """A plotly figure driven by the tick (checks the plotly alpha)."""
        return px.bar(
            x=DF["zone"].tolist(),
            y=[v + self.tick for v in DF["n"].tolist()],
            title=f"plotly tick {self.tick}",
        )


@rx.memo
def memo_table(data: pd.DataFrame) -> rx.Component:
    """A memoized component that receives a DataFrame prop."""
    return rx.data_table(data=data, pagination=False, search=False, sort=False)


class CounterCS(rx.ComponentState):
    """ComponentState rendering the same DataFrame."""

    n: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        """Build the component.

        Args:
            props: Extra props.

        Returns:
            The component.
        """
        return rx.vstack(
            rx.button(f"cs {cls.n}", on_click=cls.inc, id="cs-btn"),
            rx.data_table(data=DF, pagination=False, search=False, sort=False),
            **props,
        )


def pandas_page() -> rx.Component:
    """The QA page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("pandas + sqlmodel serializer probe"),
        rx.button("bump", on_click=PandasState.bump, id="bump"),
        rx.button("load rows", on_click=PandasState.load, id="load"),
        rx.text(f"tick=", PandasState.tick, id="tick"),
        rx.text("steady=", PandasState.steady, id="steady"),
        rx.heading("literal DataFrame", size="3"),
        rx.data_table(data=DF, pagination=False, search=False, sort=False),
        rx.heading("state-computed DataFrame", size="3"),
        rx.data_table(
            data=PandasState.frame, pagination=False, search=False, sort=False
        ),
        rx.heading("memo(DataFrame prop)", size="3"),
        memo_table(data=DF),
        rx.heading("ComponentState", size="3"),
        CounterCS.create(),
        rx.heading("recharts bar chart", size="3"),
        rx.recharts.bar_chart(
            rx.recharts.bar(data_key="n", fill="#8884d8"),
            rx.recharts.x_axis(data_key="zone"),
            rx.recharts.y_axis(),
            rx.recharts.graphing_tooltip(),
            data=PandasState.chart_data,
            width=420,
            height=220,
            id="rechart",
        ),
        rx.heading("plotly figure", size="3"),
        rx.plotly(data=PandasState.figure, width="420px", height="260px", id="plotfig"),
        rx.heading("model rows (relationship serialization)", size="3"),
        rx.cond(
            PandasState.rows,
            rx.foreach(
                PandasState.rows,
                lambda r: rx.text(r.state, " / ", r.zone, " / ", r.total_cases),
            ),
            rx.text("no rows loaded", id="norows"),
        ),
        spacing="3",
        padding="2em",
    )
