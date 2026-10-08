"""Mutable class-body defaults populated AFTER the class statement (registry / plugin / lazily loaded config).
Runs unchanged on 0.9.12, 0.10.0a4 and 0.10.0a5 (no set_default)."""
import reflex as rx

LATE_OPTIONS: list[str] = []
LATE_REG: dict[str, str] = {}
CONFIG: dict[str, str] = {}


class LateState(rx.State):
    options: list[str] = LATE_OPTIONS  # populated below, after the class
    _reg: dict[str, str] = LATE_REG  # filled by a decorator below
    _config: dict[str, str] = CONFIG  # filled at app start (lifespan task)
    field_opts: list[str] = rx.field(LATE_OPTIONS)  # same list through rx.field
    regs: str = ""
    cfg: str = ""

    @rx.event
    def show(self):
        self.regs = ",".join(sorted(self._reg)) or "<empty>"
        self.cfg = ",".join(f"{k}={v}" for k, v in sorted(self._config.items())) or "<empty>"


def register(fn):
    LATE_REG[fn.__name__] = fn.__name__
    return fn


LATE_OPTIONS.extend(["red", "green"])


@register
def plugin_a(): ...


async def load_config():
    CONFIG.update({"api": "https://x", "retries": "3"})


def index():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(LateState.options.join(",") + "|", id="late_opts"),
        rx.text(LateState.field_opts.join(",") + "|", id="late_field_opts"),
        rx.text(LateState.regs, id="late_regs"),
        rx.text(LateState.cfg, id="late_cfg"),
        rx.button("show", on_click=LateState.show, id="late_show"),
        rx.foreach(LateState.options, lambda o: rx.badge(o)),
    )


app = rx.App()
app.register_lifespan_task(load_config)
app.add_page(index)
