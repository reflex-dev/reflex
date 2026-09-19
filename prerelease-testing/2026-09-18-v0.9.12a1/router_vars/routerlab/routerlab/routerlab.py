"""Router-vars exploration app for reflex 0.9.12a1 (#7068/#7077/#7136)."""

import reflex as rx

# Guard: make sure we are NOT importing the checkout copy of reflex.
assert "/envs/" in rx.__file__, f"WRONG REFLEX: {rx.__file__}"


class State(rx.State):
    """Root state exercising every router dependency form."""

    counter: int = 0
    nav_log: list[str] = []

    # --- computed vars, one per dependency form ---

    @rx.var
    def cv_auto_path(self) -> str:
        """Auto-dep through the router property getter."""
        return f"auto:{self.router.url.path}"

    @rx.var(deps=[rx.State.router])
    def cv_deps_whole_router(self) -> str:
        """deps=[State.router] -> should cover all five fields."""
        return f"whole:{self.router.url.path}|{self.router.route_id}|sid={self.router.session.session_id[:6]}"

    @rx.var(deps=[rx.State.router.url])
    def cv_deps_router_url(self) -> str:
        """deps=[State.router.url] -> narrows to the url field."""
        return f"urlonly:{self.router.url.path}?{self.router.url.query}"

    @rx.var(deps=["router"])
    def cv_deps_legacy_string(self) -> str:
        """Legacy deps=['router'] string form -> expects a deprecation warning."""
        return f"legacy:{self.router.url.path}"

    @rx.var
    def cv_headers(self) -> str:
        h = self.router.headers
        return f"ua={(h.user_agent or '')[:24]}|xtest={getattr(h, 'raw_headers', {}).get('x-rxtest', 'MISSING')}"

    @rx.var
    def cv_session(self) -> str:
        s = self.router.session
        return f"ip={s.client_ip}|tok={s.client_token[:8]}|sid={s.session_id[:8]}"

    @rx.var
    def cv_page_params(self) -> str:
        """Deprecated self.router.page.params access."""
        return f"params={dict(self.router.page.params)}"

    @rx.var
    def cv_query_params(self) -> str:
        return f"qp={dict(self.router.url.query_parameters)}"

    @rx.var
    def cv_route_id(self) -> str:
        return f"route_id={self.router.route_id}"

    @rx.var
    def cv_frag(self) -> str:
        return f"frag={self.router.url.fragment}|origin={self.router.url.origin}"

    @rx.event
    def bump(self):
        """An event that changes NO route data."""
        self.counter += 1

    @rx.event
    def mutate_headers(self):
        """Try to corrupt the connection-scoped header cache."""
        try:
            self.router_data["headers"]["x-rxtest"] = "CORRUPTED"
            self.router_data["headers"]["user-agent"] = "CORRUPTED-UA"
        except Exception as e:  # noqa: BLE001
            self.nav_log = [*self.nav_log, f"mutate failed: {e!r}"]
        self.counter += 1

    @rx.event
    def log_nav(self):
        self.nav_log = [*self.nav_log[-6:], self.router.url.path]

    @rx.event(background=True)
    async def bg_read_router(self):
        """Background task reading the router."""
        async with self:
            p = self.router.url.path
            rid = self.router.route_id
        async with self:
            self.nav_log = [*self.nav_log[-6:], f"bg:{p}|{rid}"]

    @rx.event
    def go_about(self):
        return rx.redirect("/about")

    @rx.event
    def chain_then_nav(self):
        """Event chain: bump then navigate."""
        self.counter += 10
        return [State.log_nav, rx.redirect("/items/chained")]


class SubState(State):
    """Substate reading self.router in a handler and a computed var."""

    sub_note: str = ""

    @rx.var
    def sub_cv(self) -> str:
        return f"sub:{self.router.url.path}|{self.router.route_id}"

    @rx.event
    def read_router(self):
        self.sub_note = (
            f"handler saw {self.router.url.path} q={dict(self.router.url.query_parameters)} "
            f"params={dict(self.router.page.params)}"
        )


class ItemState(rx.State):
    """on_load handler using the deprecated page.params."""

    loaded_id: str = ""

    @rx.event
    def on_load_item(self):
        self.loaded_id = self.router.page.params.get("id", "<none>")
        if self.loaded_id == "redirectme":
            return rx.redirect("/about")


class RouterComponentState(rx.ComponentState):
    """ComponentState whose render uses State.router.url.path."""

    clicks: int = 0

    @rx.event
    def click(self):
        self.clicks += 1

    @classmethod
    def get_component(cls, **props):
        return rx.vstack(
            rx.text("CS path: ", rx.State.router.url.path, id=props.pop("path_id", "cs_path")),
            rx.text("CS clicks: ", cls.clicks, id="cs_clicks"),
            rx.button("cs-click", on_click=cls.click, id="cs_btn"),
            **props,
        )


@rx.memo
def memo_path(path: rx.Var[str], label: rx.Var[str]) -> rx.Component:
    """rx.memo component fed State.router.url.path as a prop."""
    return rx.text(f"memo[{label}]: ", path, id="memo_path")


cs = rx.State.router.session
client_state_probe = rx._x.client_state(var_name="cs_probe", default="")


def dbg(id_: str, label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label + ": ", weight="bold"),
        rx.text(value, id=id_),
        spacing="1",
    )


def common() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.link("home", href="/", id="nav_home"),
            rx.link("item1", href="/items/1", id="nav_item1"),
            rx.link("item2", href="/items/2", id="nav_item2"),
            rx.link("docs", href="/docs/a/b", id="nav_docs"),
            rx.link("search", href="/search?q=hello", id="nav_search"),
            rx.link("about", href="/about", id="nav_about"),
        ),
        dbg("cv_auto_path", "auto", State.cv_auto_path),
        dbg("cv_deps_whole_router", "whole", State.cv_deps_whole_router),
        dbg("cv_deps_router_url", "urlonly", State.cv_deps_router_url),
        dbg("cv_deps_legacy_string", "legacy", State.cv_deps_legacy_string),
        dbg("cv_headers", "headers", State.cv_headers),
        dbg("cv_session", "session", State.cv_session),
        dbg("cv_page_params", "pageparams", State.cv_page_params),
        dbg("cv_query_params", "queryparams", State.cv_query_params),
        dbg("cv_route_id", "routeid", State.cv_route_id),
        dbg("cv_frag", "frag", State.cv_frag),
        dbg("sub_cv", "subcv", SubState.sub_cv),
        dbg("sub_note", "subnote", SubState.sub_note),
        dbg("counter", "counter", State.counter),
        # class-level router access straight into a component prop
        dbg("direct_token", "direct token", rx.State.router.session.client_token),
        dbg("direct_path", "direct path", rx.State.router.url.path),
        dbg("direct_rid", "direct route_id", rx.State.router.route_id),
        # whole-router render: should still emit the pre-split object literal
        rx.box(rx.code(rx.State.router.to_string(), id="whole_router")),
        rx.cond(
            rx.State.router.url.path == "/",
            rx.text("COND: on home", id="cond_out"),
            rx.text("COND: not home", id="cond_out"),
        ),
        rx.match(
            rx.State.router.route_id,
            ("/", rx.text("MATCH:home", id="match_out")),
            ("/about", rx.text("MATCH:about", id="match_out")),
            rx.text("MATCH:other", id="match_out"),
        ),
        rx.foreach(State.nav_log, lambda s, i: rx.text(f"[{i}] ", s, class_name="navlog")),
        memo_path(path=rx.State.router.url.path, label="A"),
        memo_path(path=rx.State.router.url.path, label="B"),
        RouterComponentState.create(),
        client_state_probe,
        rx.hstack(
            rx.button("bump", on_click=State.bump, id="btn_bump"),
            rx.button("sub-read", on_click=SubState.read_router, id="btn_subread"),
            rx.button("mutate-headers", on_click=State.mutate_headers, id="btn_mutate"),
            rx.button("bg", on_click=State.bg_read_router, id="btn_bg"),
            rx.button("chain", on_click=State.chain_then_nav, id="btn_chain"),
            rx.button("redirect-about", on_click=State.go_about, id="btn_redirect"),
            rx.button(
                "set-cs",
                on_click=client_state_probe.set_value(rx.State.router.url.path),
                id="btn_cs",
            ),
            rx.text("csval: ", client_state_probe.value, id="cs_value"),
        ),
        align="start",
        spacing="1",
    )


def index() -> rx.Component:
    return rx.vstack(rx.heading("HOME", id="page_title"), common())


@rx.page(route="/items/[id]", on_load=ItemState.on_load_item)
def item_page() -> rx.Component:
    return rx.vstack(
        rx.heading("ITEM", id="page_title"),
        dbg("item_loaded_id", "on_load id", ItemState.loaded_id),
        common(),
    )


@rx.page(route="/docs/[[...splat]]")
def docs_page() -> rx.Component:
    return rx.vstack(rx.heading("DOCS", id="page_title"), common())


@rx.page(route="/search")
def search_page() -> rx.Component:
    return rx.vstack(
        rx.heading("SEARCH", id="page_title"),
        dbg("search_q", "q", rx.State.router.url.query_parameters.get("q", "<no q>")),
        common(),
    )


@rx.page(route="/about")
def about_page() -> rx.Component:
    return rx.vstack(rx.heading("ABOUT", id="page_title"), common())


app = rx.App()
app.add_page(index, route="/")
