"""Radix slider/progress in ComponentState, Shiki/markdown/moment, rx.download."""

import asyncio
import json
from typing import Any

import reflex as rx

from .common import nav


class SliderCS(rx.ComponentState):
    """Slider + progress owned by a ComponentState."""

    value: int = 50
    committed: int = 50
    changes: int = 0
    commits: int = 0
    progress: int = 0
    running: bool = False

    @rx.event
    def on_change(self, v: list[int | float]):
        self.value = int(v[0])
        self.changes += 1

    @rx.event
    def on_commit(self, v: list[int | float]):
        self.committed = int(v[0])
        self.commits += 1

    @rx.event(background=True)
    async def run_progress(self):
        async with self:
            if self.running:
                return
            self.running = True
            self.progress = 0
        for i in range(1, 11):
            await asyncio.sleep(0.3)
            async with self:
                self.progress = i * 10
        async with self:
            self.running = False

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        p = props.pop("prefix")
        return rx.vstack(
            rx.slider(
                value=[cls.value],
                on_change=cls.on_change,
                on_value_commit=cls.on_commit,
                min=0,
                max=100,
                step=5,
                id=f"{p}-slider",
                width="300px",
            ),
            rx.text("value=", cls.value, id=f"{p}-value"),
            rx.text("committed=", cls.committed, id=f"{p}-committed"),
            rx.text("changes=", cls.changes, " commits=", cls.commits, id=f"{p}-counts"),
            rx.progress(value=cls.progress, max=100, id=f"{p}-progress", width="300px"),
            rx.text("progress=", cls.progress, id=f"{p}-progress-text"),
            rx.button("run progress", on_click=cls.run_progress, id=f"{p}-run"),
        )


sl1 = SliderCS.create(prefix="sl1")
sl2 = SliderCS.create(prefix="sl2")


def radix_page() -> rx.Component:
    """Slider/progress page."""
    return rx.vstack(nav(), rx.heading("Radix slider/progress"), rx.hstack(sl1, sl2), padding="10px")


CODE_PY = "def double(x):\n    # comment\n    return x * 2\n"
CODE_JS = "const double = (x) => x * 2; // comment\n"
MD_TEXT = "# Markdown\n\nSome `inline` code.\n\n```python\nprint('fenced')  # comment\n```\n\n```javascript\nconsole.log(1)\n```\n"


class CodeState(rx.State):
    """Shiki/moment state."""

    theme: str = "github-light"
    lang: str = "python"
    code: str = CODE_PY
    tz: str = "America/New_York"
    locale: str = "fr"
    fmt: str = "dddd D MMMM YYYY HH:mm"
    date: str = "2026-01-15T12:34:56Z"
    ticks: int = 0
    moment_changes: int = 0

    @rx.event
    def switch(self):
        if self.lang == "python":
            self.theme, self.lang, self.code = "dracula", "javascript", CODE_JS
        else:
            self.theme, self.lang, self.code = "github-light", "python", CODE_PY

    @rx.event
    def switch_moment(self):
        self.tz = "Asia/Tokyo"
        self.locale = "de"
        self.fmt = "YYYY-MM-DD HH:mm z"

    @rx.event
    def bump(self):
        self.ticks += 1

    @rx.event
    def moment_changed(self, value: str):
        self.moment_changes += 1


def code_page() -> rx.Component:
    """Shiki, markdown and moment page."""
    return rx.vstack(
        nav(),
        rx.heading("Shiki / markdown / moment"),
        rx.hstack(
            rx.button("switch code", on_click=CodeState.switch, id="code-switch"),
            rx.button("switch moment", on_click=CodeState.switch_moment, id="moment-switch"),
            rx.button("bump", on_click=CodeState.bump, id="code-bump"),
            rx.text("ticks=", CodeState.ticks, id="code-ticks"),
            rx.text("theme=", CodeState.theme, " lang=", CodeState.lang, id="code-meta"),
        ),
        rx.box(rx._x.code_block(CodeState.code, language=CodeState.lang, theme=CodeState.theme), id="shiki-dyn"),
        rx.box(
            rx._x.code_block("print('x') # [!code highlight]\nprint('y')", language="python", use_transformers=True),
            id="shiki-transformers",
        ),
        rx.box(
            rx._x.code_block(
                "x = 1\n",
                language="python",
                themes={"light": "github-light", "dark": "github-dark"},
            ),
            id="shiki-themes-dict",
        ),
        rx.box(rx.markdown(MD_TEXT), id="md-fenced"),
        rx.box(
            rx.moment(CodeState.date, tz=CodeState.tz, locale=CodeState.locale, format=CodeState.fmt),
            id="m-state",
        ),
        rx.box(rx.moment(interval=1000, format="HH:mm:ss", on_change=CodeState.moment_changed), id="m-tick"),
        rx.text("moment on_change=", CodeState.moment_changes, id="m-changes"),
        rx.box(
            rx.moment(date="2026-01-01T01:30:15Z", duration="2026-01-01T00:00:00Z", format="hh:mm:ss"),
            id="m-duration",
        ),
        rx.box(rx.moment("2026-03-01T10:00:00Z", locale="ja", format="LLLL", tz="UTC"), id="m-ja"),
        padding="10px",
    )


def _payload(n: int) -> str:
    """Deterministic text with '#', '%', '%41', emoji, CJK, control-ish and quote chars."""
    unit = (
        "line #1 100% sure %41 %%25 ? & = + / \\ \" ' <tag> "
        "\U0001f600\U0001f469‍\U0001f4bb 中文 éè    "
        "\x01\x02\x1f\x7f\u0080ÿ tab\tcr\rlf\n"
    )
    reps = n // len(unit) + 1
    return (unit * reps)[:n]


class DLState(rx.State):
    """rx.download test state."""

    payload: str = ""
    size: int = 0
    items: list[dict[str, Any]] = [{"address": "12 Main St #4", "note": "100%25 sure", "emoji": "\U0001f600"}]
    data_url: str = "data:text/plain;charset=utf-8,already%20a%20data%20url%20%23hash"

    @rx.event
    def make(self, n: int):
        self.payload = _payload(int(n))
        self.size = len(self.payload)

    @rx.event
    def backend_download(self):
        return rx.download(data=self.payload, filename="backend.txt")


def download_page() -> rx.Component:
    """rx.download page."""
    return rx.vstack(
        nav(),
        rx.heading("rx.download"),
        rx.hstack(
            *[
                rx.button(f"make {n}", on_click=DLState.make(n), id=f"make-{n}")
                for n in (10_000, 500_000, 1_000_000, 2_000_000)
            ],
            rx.text("size=", DLState.size, id="dl-size"),
        ),
        rx.hstack(
            rx.button("download var", on_click=rx.download(data=DLState.payload, filename="var.txt"), id="dl-var"),
            rx.button("download list", on_click=rx.download(data=DLState.items, filename="list.json"), id="dl-list"),
            rx.button("download data-url var", on_click=rx.download(data=DLState.data_url, filename="du.txt"), id="dl-dataurl"),
            rx.button("download backend", on_click=DLState.backend_download, id="dl-backend"),
        ),
        padding="10px",
    )


def home_page() -> rx.Component:
    """Home page."""
    return rx.vstack(nav(), rx.heading("dataeditor_components cluster app"), padding="10px")


__all__ = ["code_page", "download_page", "home_page", "radix_page", "json"]
