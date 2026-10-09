"""Hydration / client-storage / on_load lifecycle probe app (identical source for 0.9.12 and 0.10.0a1)."""

import asyncio
import dataclasses
import datetime
import os
import time
import uuid

import reflex as rx

# Guard (added to the archived copy after the runs; functionally neutral): never import reflex from a checkout.
import os as _os_guard
assert f"/envs/{_os_guard.environ['RVH_VENV']}/" in rx.__file__, (_os_guard.environ.get("RVH_VENV"), rx.__file__)

# Shared mutable default (anti-pattern): mutated after class creation at import
# time and again by a lifespan task that only runs in the backend worker.
SHARED_ITEMS = ["base"]


def _tok(state: rx.State) -> str:
    try:
        return state.router.session.client_token[:8]
    except Exception:  # noqa: BLE001
        return "????????"


def _log(state: rx.State, msg: str) -> None:
    print(f"HYDTRACE {time.time():.3f} {_tok(state)} {msg}", flush=True)


@dataclasses.dataclass
class Point:
    """A dataclass-typed var."""

    x: int = 1
    y: int = 2


class State(rx.State):
    """Root state with client storage of every kind."""

    ls_plain: str = rx.LocalStorage("ls-default")
    ls_sync: str = rx.LocalStorage("sync-default", sync=True, name="hyd_sync")
    ss_val: str = rx.SessionStorage("ss-default")
    ck_val: str = rx.Cookie("ck-default", max_age=3600, path="/")
    ck_int: int = rx.Cookie("5", name="hyd_int")
    ls_same: str = rx.LocalStorage("same-value", name="hyd_same")
    ls_big: str = rx.LocalStorage("", name="hyd_big")

    counter: int = 0
    trace: list[str] = []
    load_count: int = 0
    other_count: int = 0

    # slow on_load
    slow_progress: int = 0
    slow_runs: int = 0
    # background on_load
    bg_status: str = "idle"
    # call_script result
    script_result: str = ""
    # multi on_load order
    multi_order: list[str] = []
    # dynamic route
    item_trace: list[str] = []
    docs_trace: list[str] = []
    # click-before-hydrate
    cf_loaded: bool = False
    cf_log: list[str] = []
    # gate
    gate_loads: int = 0
    # nested/failing event list
    nested_log: list[str] = []

    def _t(self, msg: str) -> None:
        self.trace.append(msg)
        _log(self, msg)

    @rx.var
    def big_len(self) -> int:
        return len(self.ls_big)

    @rx.event
    async def index_load(self):
        sub = await self.get_state(Sub)
        clean = await self.get_state(Clean)
        self.load_count += 1
        self._t(
            f"index_load#{self.load_count} ls={self.ls_plain}|sync={self.ls_sync}|ss={self.ss_val}"
            f"|ck={self.ck_val}|int={self.ck_int!r}|same={self.ls_same}|big={len(self.ls_big)}"
            f"|sub_ls={sub.sub_ls}|sub_ck={sub.sub_ck}|clean_ls={clean.clean_ls}|hyd={self.is_hydrated}"
        )

    @rx.event
    def increment(self):
        self.counter += 1

    @rx.event
    def set_values(self, tag: str):
        self.ls_plain = f"ls-{tag}"
        self.ls_sync = f"sync-{tag}"
        self.ss_val = f"ss-{tag}"
        self.ck_val = f"ck-{tag}"

    @rx.event
    def set_sync(self, v: str):
        self.ls_sync = v

    @rx.event
    def set_big(self, n: int):
        self.ls_big = "x" * int(n)

    @rx.event
    def int_plus_one(self):
        try:
            self._t(f"int_plus_one -> {self.ck_int + 1!r}")
        except Exception as ex:  # noqa: BLE001
            self._t(f"int_plus_one raised {type(ex).__name__}: {ex}")

    @rx.event
    def clear_trace(self):
        self.trace = []

    @rx.event
    def other_load(self):
        self.other_count += 1
        self._t(f"other_load#{self.other_count} path={self.router.url.path}")

    @rx.event
    def redirect_load(self):
        self._t("redirect_load")
        return rx.redirect("/other")

    @rx.event(background=True)
    async def bg_load(self):
        async with self:
            self.bg_status = "started"
            self._t("bg_load started")
        await asyncio.sleep(1.5)
        async with self:
            self.bg_status = "done"
            self._t("bg_load done")

    @rx.event
    def raise_load(self):
        self._t("raise_load about to raise")
        msg = "boom from on_load"
        raise ValueError(msg)

    @rx.event
    async def slow_load(self):
        self.slow_runs += 1
        run = self.slow_runs
        self.slow_progress = 0
        for i in range(1, 5):
            self.slow_progress = i
            self._t(f"slow_load run{run} step{i}")
            yield
            if i < 4:
                await asyncio.sleep(2)
        self._t(f"slow_load run{run} finished")

    @rx.event
    def script_load(self):
        self._t("script_load")
        return rx.call_script("21 * 2", callback=State.got_script)

    @rx.event
    def got_script(self, value):
        self.script_result = f"{value!r}"
        self._t(f"got_script {value!r}")

    @rx.event
    def multi_a(self):
        self.multi_order.append(f"A(ls={self.ls_plain})")
        self._t("multi_a")

    @rx.event
    def item_load(self):
        params = self.router.page.params
        self.item_trace.append(
            f"id={params.get('id')}|path={self.router.url.path}|url={self.router.url}"
        )
        self._t(f"item_load id={params.get('id')}")

    @rx.event
    def docs_load(self):
        params = self.router.page.params
        self.docs_trace.append(
            f"splat={params.get('splat')}|path={self.router.url.path}"
        )
        self._t(f"docs_load splat={params.get('splat')}")

    @rx.event
    async def clickfast_load(self):
        self._t("clickfast_load begin")
        await asyncio.sleep(1.0)
        self.cf_loaded = True
        self.cf_log.append("load")
        self._t("clickfast_load end")

    @rx.event
    def cf_click(self, which: str):
        self.cf_log.append(f"click-{which}(loaded={self.cf_loaded},hyd={self.is_hydrated})")
        self._t(f"cf_click {which} loaded={self.cf_loaded} hyd={self.is_hydrated}")

    @rx.event
    async def gate_load(self):
        await asyncio.sleep(0.8)
        self.gate_loads += 1
        self._t(f"gate_load#{self.gate_loads}")

    @rx.event
    def nested_a(self):
        self.nested_log.append("a")

    @rx.event
    def nested_b(self):
        self.nested_log.append("b")

    @rx.event
    def nested_c(self):
        self.nested_log.append("c")


class Sub(State):
    """Substate with client storage AND a per-session (non-deterministic) default."""

    sub_ls: str = rx.LocalStorage(
        os.environ.get("HYD_SUB_LS_DEFAULT", "sub-ls-default"), name="hyd_sub_ls"
    )
    sub_ck: str = rx.Cookie("sub-ck-default", name="hyd_sub_ck", max_age=600)
    sub_ss: str = rx.SessionStorage("sub-ss-default", name="hyd_sub_ss")
    sub_uuid: str = rx.field(default_factory=lambda: uuid.uuid4().hex)
    sub_saw: str = ""

    @rx.event
    def set_sub(self, tag: str):
        self.sub_ls = f"sub-ls-{tag}"
        self.sub_ck = f"sub-ck-{tag}"

    @rx.event
    async def multi_b(self):
        root = await self.get_state(State)
        root.multi_order.append(f"B(root_ls={root.ls_plain},sub_ls={self.sub_ls})")
        self.sub_saw = f"root_ls={root.ls_plain}"
        root._t("multi_b")


class Clean(State):
    """Substate with only client storage and deterministic defaults."""

    clean_ls: str = rx.LocalStorage("clean-default", name="hyd_clean_ls")
    clean_ck: str = rx.Cookie("clean-ck-default", name="hyd_clean_ck")


class LsLoad(State):
    """A state whose own on_load reads its own LocalStorage var (brief item 8)."""

    lsl_val: str = rx.LocalStorage("lsl-default", name="hyd_lsl")
    lsl_saw: list[str] = []

    @rx.event
    def lsl_load(self):
        self.lsl_saw.append(f"saw={self.lsl_val}")
        _log(self, f"lsl_load saw={self.lsl_val}")

    @rx.event
    def set_lsl(self, v: str):
        self.lsl_val = v


class Defaults(State):
    """Defaults that differ from (or are not stable across) compiled defaults."""

    session_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)
    created: datetime.datetime = rx.field(default_factory=datetime.datetime.now)
    fixed_dt: datetime.datetime = datetime.datetime(2020, 1, 2, 3, 4, 5)
    env_val: str = os.environ.get("HYD_ENV_DEFAULT", "env-unset")
    items: list[str] = SHARED_ITEMS
    mapping: dict[str, int] = {"b": 2, "a": 1}
    point: Point = Point()
    flt: float = 1.0
    pid_default: str = str(os.getpid())

    @rx.var
    def summary(self) -> str:
        return (
            f"n={len(self.items)} env={self.env_val} sum={sum(self.mapping.values())}"
            f" pt={self.point.x + self.point.y}"
        )

    @rx.event
    async def report_defaults(self):
        import json

        root = await self.get_state(State)
        root._t(
            "backend_defaults="
            + json.dumps({
                "session_id": self.session_id,
                "created": str(self.created),
                "env_val": self.env_val,
                "items": self.items,
                "mapping": self.mapping,
                "pid_default": self.pid_default,
                "summary": self.summary,
                "shared_now": SHARED_ITEMS,
            })
        )

    @rx.event
    def mutate_shared(self):
        SHARED_ITEMS.append(f"runtime-{len(SHARED_ITEMS)}")
        _log(self, f"mutate_shared -> {SHARED_ITEMS}")


# Anti-pattern: mutate the shared default after the state class was created.
SHARED_ITEMS.append("import-mutated")


class Up(State):
    """Upload state for the #7357 in-flight upload + navigation scenario."""

    up_status: str = "none"

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        # Buffered upload whose handler stays in flight for ~7s.
        self.up_status = f"started {len(files)}"
        _log(self, "upload started")
        yield
        await asyncio.sleep(7)
        self.up_status = f"done {len(files)}"
        _log(self, "upload done")


class StorageBox(rx.ComponentState):
    """ComponentState with its own LocalStorage var."""

    box_ls: str = rx.LocalStorage("box-default")
    box_count: int = 0

    @rx.event
    def set_box(self, v: str):
        self.box_ls = v
        self.box_count += 1

    @classmethod
    def get_component(cls, label: str = "x", **props):
        return rx.hstack(
            rx.text("box ", label, ": "),
            rx.text(cls.box_ls, id=f"box-{label}-ls"),
            rx.text(cls.box_count, id=f"box-{label}-count"),
            rx.button(
                f"set box {label}",
                on_click=cls.set_box(f"box-{label}-set"),
                id=f"box-{label}-btn",
            ),
            **props,
        )


box_a = StorageBox.create(label="a")
box_b = StorageBox.create(label="b")


def nav() -> rx.Component:
    links = [
        ("/", "home"),
        ("/other", "other"),
        ("/redir", "redir"),
        ("/bgload", "bgload"),
        ("/raise", "raise"),
        ("/slow", "slow"),
        ("/multi", "multi"),
        ("/script", "script"),
        ("/items/1", "item1"),
        ("/items/2", "item2"),
        ("/docs/a/b", "docsab"),
        ("/docs", "docsroot"),
        ("/lsload", "lsload"),
        ("/defaults", "defaults"),
        ("/clickfast", "clickfast"),
        ("/gate", "gate"),
        ("/upload", "upload"),
        ("/nested", "nested"),
    ]
    return rx.hstack(
        *[rx.link(label, href=href, id=f"nav-{label}") for href, label in links],
        wrap="wrap",
        spacing="2",
    )


def common() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.text(rx.cond(State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(State.counter, id="counter"),
        rx.button("increment", on_click=State.increment, id="inc"),
        rx.text(State.trace.to_string(), id="trace", font_size="9px"),
        rx.button("clear trace", on_click=State.clear_trace, id="clear-trace"),
    )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("index", id="page-index"),
        common(),
        rx.text(State.ls_plain, id="ls-plain"),
        rx.text(State.ls_sync, id="ls-sync"),
        rx.text(State.ss_val, id="ss-val"),
        rx.text(State.ck_val, id="ck-val"),
        rx.text(State.ck_int, id="ck-int"),
        rx.text(State.ck_int + 1, id="ck-int-plus"),
        rx.text(State.ls_same, id="ls-same"),
        rx.text(State.big_len, id="big-len"),
        rx.text(Sub.sub_ls, id="sub-ls"),
        rx.text(Sub.sub_ck, id="sub-ck"),
        rx.text(Sub.sub_ss, id="sub-ss"),
        rx.text(Sub.sub_uuid, id="sub-uuid"),
        rx.text(Clean.clean_ls, id="clean-ls"),
        rx.text(Clean.clean_ck, id="clean-ck"),
        rx.text(State.load_count, id="load-count"),
        rx.input(id="tag-input", default_value="t1"),
        rx.button("set values", on_click=State.set_values("A"), id="set-values"),
        rx.button("set sync B", on_click=State.set_sync("sync-from-B"), id="set-sync-b"),
        rx.button("set sub", on_click=Sub.set_sub("S1"), id="set-sub"),
        rx.button("set big", on_click=State.set_big(300000), id="set-big"),
        rx.button("int+1", on_click=State.int_plus_one, id="int-plus-one"),
        rx.button(
            "remove ls_plain",
            on_click=rx.remove_local_storage("reflex___state____state.hydapp___hydapp____state.ls_plain_rx_state_"),
            id="rm-ls",
        ),
        box_a,
        box_b,
    )


def other() -> rx.Component:
    return rx.vstack(
        rx.heading("other", id="page-other"),
        common(),
        rx.text(State.other_count, id="other-count"),
        rx.text(State.slow_progress, id="slow-progress-other"),
    )


def redir() -> rx.Component:
    return rx.vstack(rx.heading("redir", id="page-redir"), common())


def bgload() -> rx.Component:
    return rx.vstack(
        rx.heading("bgload", id="page-bgload"),
        common(),
        rx.text(State.bg_status, id="bg-status"),
    )


def raise_page() -> rx.Component:
    return rx.vstack(rx.heading("raise", id="page-raise"), common())


def slow() -> rx.Component:
    return rx.vstack(
        rx.heading("slow", id="page-slow"),
        common(),
        rx.text(State.slow_progress, id="slow-progress"),
        rx.text(State.slow_runs, id="slow-runs"),
    )


def multi() -> rx.Component:
    return rx.vstack(
        rx.heading("multi", id="page-multi"),
        common(),
        rx.text(State.multi_order.to_string(), id="multi-order"),
        rx.text(Sub.sub_saw, id="sub-saw"),
    )


def script() -> rx.Component:
    return rx.vstack(
        rx.heading("script", id="page-script"),
        common(),
        rx.text(State.script_result, id="script-result"),
    )


def item() -> rx.Component:
    return rx.vstack(
        rx.heading("item", id="page-item"),
        common(),
        rx.text(State.item_trace.to_string(), id="item-trace"),
        rx.text(State.router.page.params.to_string(), id="item-params"),
    )


def docs() -> rx.Component:
    return rx.vstack(
        rx.heading("docs", id="page-docs"),
        common(),
        rx.text(State.docs_trace.to_string(), id="docs-trace"),
    )


def lsload() -> rx.Component:
    return rx.vstack(
        rx.heading("lsload", id="page-lsload"),
        common(),
        rx.text(LsLoad.lsl_val, id="lsl-val"),
        rx.text(LsLoad.lsl_saw.to_string(), id="lsl-saw"),
        rx.button("set lsl", on_click=LsLoad.set_lsl("lsl-set-by-ui"), id="set-lsl"),
    )


def defaults() -> rx.Component:
    return rx.vstack(
        rx.heading("defaults", id="page-defaults"),
        common(),
        rx.text(Defaults.session_id, id="d-session-id"),
        rx.text(Defaults.created.to_string(), id="d-created"),
        rx.text(Defaults.fixed_dt.to_string(), id="d-fixed-dt"),
        rx.text(Defaults.env_val, id="d-env"),
        rx.text(Defaults.items.to_string(), id="d-items"),
        rx.text(Defaults.mapping.to_string(), id="d-mapping"),
        rx.text(Defaults.point.to_string(), id="d-point"),
        rx.text(Defaults.flt, id="d-flt"),
        rx.text(Defaults.pid_default, id="d-pid"),
        rx.text(Defaults.summary, id="d-summary"),
        rx.button("mutate shared", on_click=Defaults.mutate_shared, id="d-mutate"),
        rx.button("report", on_click=Defaults.report_defaults, id="d-report"),
    )


def clickfast() -> rx.Component:
    return rx.vstack(
        rx.heading("clickfast", id="page-clickfast"),
        rx.button("always", on_click=State.cf_click("always"), id="cf-always"),
        rx.cond(
            State.is_hydrated,
            rx.button("gated", on_click=State.cf_click("gated"), id="cf-gated"),
            rx.text("not hydrated", id="cf-wait"),
        ),
        rx.text(State.cf_log.to_string(), id="cf-log"),
        common(),
    )


def gate() -> rx.Component:
    return rx.vstack(
        rx.heading("gate", id="page-gate"),
        rx.cond(
            State.is_hydrated,
            rx.text("CONTENT", id="gate-content"),
            rx.spinner(id="gate-spinner"),
        ),
        rx.text(State.gate_loads, id="gate-loads"),
        common(),
    )


def upload_page() -> rx.Component:
    return rx.vstack(
        rx.heading("upload", id="page-upload"),
        common(),
        rx.upload(rx.text("drop"), id="up1"),
        rx.button(
            "do upload",
            on_click=Up.handle_upload(rx.upload_files(upload_id="up1")),
            id="do-upload",
        ),
        rx.text(Up.up_status, id="up-status"),
        rx.text(State.slow_progress, id="slow-progress-upload"),
    )


def nested() -> rx.Component:
    return rx.vstack(
        rx.heading("nested", id="page-nested"),
        common(),
        rx.button(
            "nested list",
            on_click=[State.nested_a, State.nested_b, State.nested_c],
            id="nested-btn",
        ),
        rx.button(
            "failing then ok",
            on_click=[rx.set_value("does-not-exist", "x"), State.nested_c],
            id="fail-then-ok",
        ),
        rx.text(State.nested_log.to_string(), id="nested-log"),
    )


async def mutate_in_lifespan():
    # Backend-worker-only mutation of the shared default, after compile.
    SHARED_ITEMS.append("lifespan-mutated")
    print(f"HYDTRACE lifespan mutated SHARED_ITEMS={SHARED_ITEMS}", flush=True)


app = rx.App()
app.register_lifespan_task(mutate_in_lifespan)
app.add_page(index, route="/", on_load=State.index_load)
app.add_page(other, route="/other", on_load=State.other_load)
app.add_page(redir, route="/redir", on_load=State.redirect_load)
app.add_page(bgload, route="/bgload", on_load=State.bg_load)
app.add_page(raise_page, route="/raise", on_load=State.raise_load)
app.add_page(slow, route="/slow", on_load=State.slow_load)
app.add_page(multi, route="/multi", on_load=[State.multi_a, Sub.multi_b])
app.add_page(script, route="/script", on_load=State.script_load)
app.add_page(item, route="/items/[id]", on_load=State.item_load)
app.add_page(docs, route="/docs/[[...splat]]", on_load=State.docs_load)
app.add_page(lsload, route="/lsload", on_load=LsLoad.lsl_load)
app.add_page(defaults, route="/defaults")
app.add_page(clickfast, route="/clickfast", on_load=State.clickfast_load)
app.add_page(gate, route="/gate", on_load=State.gate_load)
app.add_page(upload_page, route="/upload")
app.add_page(nested, route="/nested")
