"""Reflex app exercising the reflex-otel instrumentation."""

import asyncio
import os

import reflex as rx

assert "/envs/otel/" in rx.__file__ or "/envs/" in rx.__file__, rx.__file__

MODE = os.environ.get("OTEL_TEST_MODE", "programmatic")

if MODE == "programmatic":
    from otelapp.telemetry import setup

    tracer_provider, meter_provider = setup()
    from reflex_otel import ReflexInstrumentor

    ReflexInstrumentor().instrument(
        tracer_provider=tracer_provider, meter_provider=meter_provider
    )
    # A second instrument() must be a silent no-op.
    ReflexInstrumentor().instrument(
        tracer_provider=tracer_provider, meter_provider=meter_provider
    )
elif MODE == "envvar":
    from reflex_otel import ReflexInstrumentor

    ReflexInstrumentor().instrument()
elif MODE == "off":
    pass


class Other(rx.State):
    """Second state, target of chained events."""

    chained: int = 0

    @rx.event
    def h(self):
        """Chained handler."""
        self.chained += 1

    @rx.event
    def deep(self):
        """Chained handler that chains again."""
        self.chained += 10
        yield Other.h()


class S(rx.State):
    """Main state."""

    count: int = 0
    log: list[str] = []
    bg_ticks: int = 0
    uploaded: str = ""
    loaded: int = 0

    @rx.event
    def inc(self):
        """Plain increment."""
        self.count += 1

    @rx.event
    def chain(self):
        """Chain into Other.h."""
        self.count += 1
        yield Other.h()
        yield Other.deep()

    @rx.event
    def boom(self):
        """Raise on purpose."""
        msg = "boom from handler"
        raise ValueError(msg)

    @rx.event
    def user_span(self):
        """Create a user span inside a handler."""
        from opentelemetry import trace

        tracer = trace.get_tracer("my.app")
        with tracer.start_as_current_span("user.work") as span:
            span.set_attribute("user.attr", "hello")
            self.count += 100
        yield Other.h()

    @rx.event(background=True)
    async def bg(self):
        """Background task that updates state a few times."""
        for _ in range(3):
            async with self:
                self.bg_ticks += 1
            await asyncio.sleep(0.05)
        async with self:
            self.log = [*self.log, "bg done"]

    @rx.event
    def on_load_second(self):
        """on_load handler for /second."""
        self.loaded += 1

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle an upload."""
        names = []
        for f in files:
            data = await f.read()
            names.append(f"{f.name}:{len(data)}")
        self.uploaded = ",".join(names)


def index() -> rx.Component:
    """Main page."""
    return rx.vstack(
        rx.heading("otel test app HOTRELOAD"),
        rx.text(S.count, id="count"),
        rx.text(Other.chained, id="chained"),
        rx.text(S.bg_ticks, id="bg_ticks"),
        rx.text(S.uploaded, id="uploaded"),
        rx.button("inc", on_click=S.inc, id="btn-inc"),
        rx.button("chain", on_click=S.chain, id="btn-chain"),
        rx.button("bg", on_click=S.bg, id="btn-bg"),
        rx.button("boom", on_click=S.boom, id="btn-boom"),
        rx.button("userspan", on_click=S.user_span, id="btn-userspan"),
        rx.upload(
            rx.text("drop"),
            rx.button("select", id="btn-select"),
            id="up1",
            multiple=False,
        ),
        rx.button(
            "upload",
            on_click=S.handle_upload(rx.upload_files(upload_id="up1")),
            id="btn-upload",
        ),
        rx.link("second", href="/second", id="link-second"),
        id="root",
    )


def second() -> rx.Component:
    """Second page with on_load."""
    return rx.vstack(
        rx.heading("second page"),
        rx.text(S.loaded, id="loaded"),
        rx.link("home", href="/", id="link-home"),
    )


def report_frontend_exception(exception: Exception) -> None:
    """Frontend exception handler."""
    print(f"[FRONTEND_EXC] {type(exception).__name__}: {exception}", flush=True)


def report_backend_exception(exception: Exception) -> None:
    """Backend exception handler."""
    print(f"[BACKEND_EXC] {type(exception).__name__}: {exception}", flush=True)


async def _flush(request):
    """Force-flush the SDK providers so the dump files are current."""
    from starlette.responses import JSONResponse

    from otelapp import telemetry
    import reflex_base.otel as o

    ok = {"pid": os.getpid(), "dump_dir": str(telemetry.DUMP_DIR)}
    if telemetry.TRACER_PROVIDER is not None:
        ok["traces"] = telemetry.TRACER_PROVIDER.force_flush(5000)
    if telemetry.METER_PROVIDER is not None:
        ok["metrics"] = telemetry.METER_PROVIDER.force_flush(5000)
    ok["otel_enabled"] = o.enabled
    ok["asgi_middleware"] = repr(o.asgi_middleware)
    from opentelemetry import trace as _t

    ok["global_tracer_provider"] = type(_t.get_tracer_provider()).__name__
    return JSONResponse(ok)


def _api():
    from starlette.applications import Starlette
    from starlette.routing import Route

    return Starlette(routes=[Route("/otel/flush", _flush)])


app = rx.App(
    frontend_exception_handler=report_frontend_exception,
    backend_exception_handler=report_backend_exception,
    api_transformer=_api(),
)
app.add_page(index, route="/")
app.add_page(second, route="/second", on_load=S.on_load_second)


class Counter(rx.ComponentState):
    """Per-instance component state."""

    n: int = 0

    @rx.event
    def bump(self):
        """Increment this instance."""
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        """Render the counter."""
        return rx.hstack(
            rx.text(cls.n, id=props.get("label", "cs") + "-val"),
            rx.button("+", on_click=cls.bump, id=props.get("label", "cs") + "-btn"),
        )


class ComboState(rx.State):
    """State for the combo page."""

    items: list[str] = ["a", "b", "c"]
    show: bool = True

    @rx.event
    def toggle(self):
        """Flip the cond."""
        self.show = not self.show

    @rx.event
    def add(self):
        """Append an item."""
        self.items = [*self.items, f"i{len(self.items)}"]


@rx.memo
def row(text: str) -> rx.Component:
    """Memoized row."""
    return rx.text(text, class_name="row")


CS = rx._x.client_state("combo_cs", default="init")


def combo() -> rx.Component:
    """Page combining ComponentState, memo, foreach, cond and client_state."""
    return rx.vstack(
        rx.heading("combo"),
        Counter.create(label="one"),
        Counter.create(label="two"),
        rx.foreach(ComboState.items, lambda t: row(text=t)),
        rx.cond(ComboState.show, rx.text("SHOWN", id="cond"), rx.text("HIDDEN", id="cond")),
        rx.button("toggle", on_click=ComboState.toggle, id="btn-toggle"),
        rx.button("add", on_click=ComboState.add, id="btn-add"),
        CS,
        rx.text(CS.value, id="cs-value"),
        rx.button("setcs", on_click=CS.set_value("from-client"), id="btn-setcs"),
        rx.link("home", href="/", id="link-home"),
    )


app.add_page(combo, route="/combo")
