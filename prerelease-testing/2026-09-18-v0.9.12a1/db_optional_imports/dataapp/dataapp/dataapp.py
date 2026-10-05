"""pandas / plotly / Pillow on-demand serializer exploration."""

import asyncio
import sys

import reflex as rx

WATCH = {"pandas", "PIL", "plotly", "numpy", "sqlalchemy", "sqlmodel"}


def loaded_optional() -> list[str]:
    return sorted({m.split(".")[0] for m in sys.modules if m.split(".")[0] in WATCH})


MODULES_AT_IMPORT = loaded_optional()

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from PIL import Image  # noqa: E402

MODULES_AFTER_DATA_IMPORT = loaded_optional()

EMPTY_DF = pd.DataFrame({"n": [], "sq": [], "label": []})
EMPTY_FIG = go.Figure()
BASE_IMG = Image.new("RGB", (64, 64), (30, 30, 30))


class State(rx.State):
    df: pd.DataFrame = EMPTY_DF
    fig: go.Figure = EMPTY_FIG
    img: Image.Image = BASE_IMG
    n: int = 3
    modules_at_import: list[str] = MODULES_AT_IMPORT
    modules_after_data_import: list[str] = MODULES_AFTER_DATA_IMPORT
    modules_now: list[str] = []
    status: str = "idle"
    bg_status: str = ""
    rows_rendered: int = 0

    def refresh_modules(self):
        self.modules_now = loaded_optional()

    def make_df(self):
        self.n += 1
        self.df = pd.DataFrame(
            {
                "n": list(range(self.n)),
                "sq": [i * i for i in range(self.n)],
                "label": [f"row-{i}" for i in range(self.n)],
            }
        )
        self.rows_rendered = self.n
        self.status = f"df {self.n} rows"
        self.refresh_modules()

    def make_fig(self):
        xs = list(range(self.n))
        self.fig = go.Figure(data=[go.Bar(x=xs, y=[i * i for i in xs])])
        self.fig.update_layout(title=f"squares n={self.n}")
        self.status = f"fig n={self.n}"
        self.refresh_modules()

    def make_img(self):
        shade = (self.n * 25) % 255
        self.img = Image.new("RGB", (64, 64), (shade, 120, 255 - shade))
        self.status = f"img shade={shade}"
        self.refresh_modules()

    def all_three(self):
        """Event chain across all three optional serializers."""
        self.make_df()
        yield State.make_fig
        yield State.make_img

    @rx.event(background=True)
    async def bg_build(self):
        """First serialization of all three inside a background task."""
        await asyncio.sleep(0.1)
        async with self:
            self.bg_status = "building"
        df = pd.DataFrame({"n": [1, 2, 3], "sq": [1, 4, 9], "label": ["bg-a", "bg-b", "bg-c"]})
        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[9, 4, 1])])
        img = Image.new("RGB", (64, 64), (200, 40, 40))
        async with self:
            self.df = df
            self.fig = fig
            self.img = img
            self.rows_rendered = 3
            self.bg_status = "bg built df+fig+img"
            self.refresh_modules()


@rx.memo
def memo_caption(text: str) -> rx.Component:
    return rx.text(text, class_name="memo-caption")


class CounterCS(rx.ComponentState):
    clicks: int = 0

    def bump(self):
        self.clicks += 1

    @classmethod
    def get_component(cls, **props):
        return rx.button(
            "cs clicks: ", cls.clicks.to_string(), on_click=cls.bump, **props
        )


def index() -> rx.Component:
    return rx.container(
        rx.heading("optional data serializers", size="5"),
        rx.hstack(
            rx.button("df", on_click=State.make_df, id="btn-df"),
            rx.button("fig", on_click=State.make_fig, id="btn-fig"),
            rx.button("img", on_click=State.make_img, id="btn-img"),
            rx.button("all", on_click=State.all_three, id="btn-all"),
            rx.button("bg", on_click=State.bg_build, id="btn-bg"),
            CounterCS.create(id="btn-cs"),
            wrap="wrap",
        ),
        rx.text("status: ", State.status, id="status"),
        rx.text("bg: ", State.bg_status, id="bg-status"),
        memo_caption(text="memoized caption"),
        rx.divider(),
        rx.heading("data_table", size="3"),
        rx.box(rx.data_table(data=State.df, pagination=False, search=False, sort=False), id="dt"),
        rx.heading("plotly", size="3"),
        rx.box(rx.plotly(data=State.fig, width="400px", height="260px"), id="plot"),
        rx.heading("image", size="3"),
        rx.box(rx.image(src=State.img, width="64px", height="64px", id="img-el"), id="imgbox"),
        rx.cond(
            State.rows_rendered > 0,
            rx.text("has rows: ", State.rows_rendered.to_string(), id="hasrows"),
            rx.text("no rows", id="hasrows"),
        ),
        rx.divider(),
        rx.text("mods at import: ", State.modules_at_import.join(","), id="mods-import"),
        rx.text("mods after data import: ", State.modules_after_data_import.join(","), id="mods-after"),
        rx.text("mods now: ", State.modules_now.join(","), id="mods-now"),
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/", on_load=State.refresh_modules)
