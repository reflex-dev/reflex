"""Route-matching memoization exercise app (PR #7025): ~150 static pages + dynamic routes."""

from __future__ import annotations

import json

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__

N_STATIC = 150


class RouteState(rx.State):
    visits: list[str] = []
    n_loads: int = 0

    @rx.event
    def record(self):
        self.n_loads += 1
        p = self.router.page
        self.visits.append(
            f"{self.n_loads}|path={p.path}|raw={p.raw_path}|full={p.full_path}"
            f"|params={json.dumps(p.params, sort_keys=True, default=str)}"
            f"|route_id={getattr(self.router, 'route_id', '?')}"
        )

    @rx.event
    def clear(self):
        self.visits = []
        self.n_loads = 0

    @rx.var
    def last_visit(self) -> str:
        return self.visits[-1] if self.visits else ""


def layout(title: str) -> rx.Component:
    return rx.vstack(
        rx.heading(title, id="title"),
        rx.hstack(
            rx.link("home", href="/", id="l-home"),
            rx.link("item/1", href="/item/1", id="l-item1"),
            rx.link("item/2", href="/item/2", id="l-item2"),
            rx.link("item/2?q=x#frag", href="/item/2?q=x&z=9#frag", id="l-item2q"),
            rx.link("docs", href="/docs", id="l-docs"),
            rx.link("docs/a/b", href="/docs/a/b", id="l-docsab"),
            rx.link("posts/all/7", href="/posts/all/7", id="l-postsall"),
            rx.link("posts/all", href="/posts/all", id="l-postsallbare"),
            rx.link("posts/42", href="/posts/42", id="l-posts42"),
            rx.link("static-0", href="/static-0", id="l-s0"),
            rx.link("static-149", href="/static-149", id="l-s149"),
            rx.link("apple", href="/apple", id="l-apple"),
            rx.link("app", href="/app", id="l-app"),
            wrap="wrap",
        ),
        rx.button("clear", on_click=RouteState.clear, id="clear"),
        rx.text("n_loads=", RouteState.n_loads, id="n_loads"),
        rx.text("last=", RouteState.last_visit, id="last"),
        rx.text("visits=", RouteState.visits.join(" ;; "), id="visits"),
    )


app = rx.App()
app.add_page(lambda: layout("index"), route="/", on_load=RouteState.record)
for i in range(N_STATIC):
    app.add_page(
        (lambda i=i: layout(f"static-{i}")), route=f"/static-{i}", on_load=RouteState.record
    )
app.add_page(lambda: layout("item"), route="/item/[id]", on_load=RouteState.record)
app.add_page(lambda: layout("docs"), route="/docs/[[...splat]]", on_load=RouteState.record)
app.add_page(lambda: layout("posts-all"), route="/posts/all/[x]", on_load=RouteState.record)
app.add_page(lambda: layout("posts-id"), route="/posts/[id]", on_load=RouteState.record)
app.add_page(lambda: layout("apple"), route="/apple", on_load=RouteState.record)
app.add_page(lambda: layout("app-route"), route="/app", on_load=RouteState.record)
