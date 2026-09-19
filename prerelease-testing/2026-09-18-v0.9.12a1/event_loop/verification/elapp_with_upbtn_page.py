"""event_loop cluster probe app for reflex 0.9.12a1.

Pages:
  /uncached   -> #6946 uncached-var delta dedupe
  /supersede  -> #7168 supersedes ordering by root generation
  /recursion  -> #7145 deep self-chain RecursionError
  /callback   -> #7156 / #7157 callback event routing (call_script cb, toast action/cancel)
  /filtered   -> #6946 interaction with a downstream get_delta filter (handover lead)
"""

import asyncio
import reflex as rx

assert "/envs/shared/" in rx.__file__ or "/envs/" in rx.__file__, rx.__file__


# ----------------------------------------------------------------- /uncached


class UC(rx.State):
    """Uncached computed var dedupe probe."""

    counter: int = 0
    nonce: int = 0
    flip: bool = False

    @rx.var(cache=False)
    def u_stable(self) -> str:
        """Never changes."""
        return "STABLE"

    @rx.var(cache=False)
    def u_derived(self) -> str:
        """Changes once every 3 bumps."""
        return f"d{self.counter // 3}"

    @rx.var(cache=False)
    def u_alt(self) -> str:
        """A -> B -> A (returns to an earlier value)."""
        return "A" if self.counter % 2 == 0 else "B"

    @rx.var(cache=False)
    def u_nan(self) -> float:
        """NaN is never == itself."""
        return float("nan")

    @rx.var(cache=False)
    def u_list(self) -> list[int]:
        """Fresh list object, equal contents."""
        return [1, 2, 3]

    @rx.var(cache=False)
    def u_dict_order(self) -> dict[str, int]:
        """Same contents, different insertion order per bump."""
        if self.counter % 2:
            return {"b": 2, "a": 1}
        return {"a": 1, "b": 2}

    @rx.var(cache=False)
    async def u_async(self) -> str:
        """Async uncached var, changes every 4 bumps."""
        await asyncio.sleep(0)
        return f"as{self.counter // 4}"

    @rx.event
    def bump(self):
        self.counter += 1

    @rx.event
    def touch_unrelated(self):
        self.nonce += 1

    @rx.event
    def do_nothing(self):
        """No var changes at all."""

    @rx.event
    def reset_all(self):
        self.counter = 0
        self.nonce = 0


class UCChild(UC):
    """Substate: uncached var reading a parent state var."""

    @rx.var(cache=False)
    def u_parent(self) -> str:
        return f"p{self.counter}"


class Unkeyable(rx.State):
    """Isolated so a serialization failure cannot break the other probes."""

    n: int = 0

    @rx.var(cache=False)
    def u_obj(self) -> complex:
        return complex(self.n, 1)

    @rx.event
    def bump_obj(self):
        self.n += 1


def _row(label: str, value) -> rx.Component:
    return rx.hstack(
        rx.text(label, width="9em", font_family="monospace"),
        rx.text(value, id=f"v-{label}", font_family="monospace"),
        spacing="2",
    )


def uncached_page() -> rx.Component:
    return rx.vstack(
        rx.heading("uncached #6946"),
        rx.hstack(
            rx.button("bump", id="bump", on_click=UC.bump),
            rx.button("touch", id="touch", on_click=UC.touch_unrelated),
            rx.button("noop", id="noop", on_click=UC.do_nothing),
            rx.button("reset", id="reset", on_click=UC.reset_all),
            rx.button("bump-obj", id="bumpobj", on_click=Unkeyable.bump_obj),
        ),
        _row("counter", UC.counter),
        _row("nonce", UC.nonce),
        _row("u_stable", UC.u_stable),
        _row("u_derived", UC.u_derived),
        _row("u_alt", UC.u_alt),
        _row("u_nan", UC.u_nan.to_string()),
        _row("u_list", UC.u_list.to_string()),
        _row("u_dict", UC.u_dict_order.to_string()),
        _row("u_async", UC.u_async),
        _row("u_parent", UCChild.u_parent),
        _row("u_obj", Unkeyable.u_obj.to_string()),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


# ---------------------------------------------------------------- /supersede


class SS(rx.State):
    """Supersedes ordering probe (#7168)."""

    log: list[str] = []
    polling: bool = False
    poll_n: int = 0

    @rx.event
    def clear_log(self):
        self.log = []
        self.polling = False
        self.poll_n = 0

    def _append(self, msg: str):
        self.log = [*self.log, msg]

    @rx.event(supersedes=True, background=True)
    async def refresh(self, tag: str):
        async with self:
            self._append(f"{tag}:start")
        try:
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            async with self:
                self._append(f"{tag}:CANCELLED")
            raise
        async with self:
            self._append(f"{tag}:done")

    @rx.event(supersedes=True)
    async def frefresh(self, tag: str):
        """Foreground superseding handler."""
        self._append(f"F{tag}:start")
        yield
        try:
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            self._append(f"F{tag}:CANCELLED")
            raise
        self._append(f"F{tag}:done")
        yield

    @rx.event
    def chain(self, tag: str):
        """Root chain that yields the shared superseding child."""
        self._append(f"chain{tag}:root")
        yield SS.refresh(f"c{tag}")

    @rx.event
    def fanout(self):
        """Sibling fan-out from one parent: both must run."""
        self._append("fanout:root")
        return [SS.refresh("x"), SS.refresh("y")]

    @rx.event(background=True)
    async def slow_stale(self):
        """Deliberately slow chain that enqueues refresh AFTER a newer chain."""
        async with self:
            self._append("slow:root")
        await asyncio.sleep(3.0)
        async with self:
            self._append("slow:enqueue")
        yield SS.refresh("stale")

    @rx.event(supersedes=True, background=True)
    async def poll(self):
        """Self-chaining superseding poll loop."""
        async with self:
            if not self.polling:
                return
            self.poll_n += 1
            n = self.poll_n
            self._append(f"poll{n}")
        await asyncio.sleep(0.4)
        yield SS.poll

    @rx.event
    def start_poll(self):
        self.polling = True
        self.poll_n = 0
        return SS.poll

    @rx.event
    def stop_poll(self):
        self.polling = False


def supersede_page() -> rx.Component:
    return rx.vstack(
        rx.heading("supersedes #7168"),
        rx.hstack(
            rx.button("rootA", id="rootA", on_click=SS.refresh("A")),
            rx.button("rootB", id="rootB", on_click=SS.refresh("B")),
            rx.button("chainA", id="chainA", on_click=SS.chain("A")),
            rx.button("chainB", id="chainB", on_click=SS.chain("B")),
            rx.button("fanout", id="fanout", on_click=SS.fanout),
        ),
        rx.hstack(
            rx.button("slow-stale", id="slow", on_click=SS.slow_stale),
            rx.button("fgA", id="fgA", on_click=SS.frefresh("A")),
            rx.button("fgB", id="fgB", on_click=SS.frefresh("B")),
            rx.button("start-poll", id="startpoll", on_click=SS.start_poll),
            rx.button("stop-poll", id="stoppoll", on_click=SS.stop_poll),
            rx.button("clear", id="clear", on_click=SS.clear_log),
        ),
        rx.text(SS.log.to_string(), id="sslog", font_family="monospace"),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


# ---------------------------------------------------------------- /recursion


class RC(rx.State):
    """Deep self-chain probe (#7145)."""

    n: int = 0
    limit: int = 3000
    running: bool = False
    finished: bool = False

    @rx.event
    def on_load_start(self):
        self.n = 0
        self.finished = False
        self.running = True
        return RC.tick

    @rx.event
    async def tick(self):
        if not self.running:
            return
        await asyncio.sleep(0.002)
        self.n += 1
        if self.n >= self.limit:
            self.running = False
            self.finished = True
            return
        yield RC.tick

    @rx.event
    def stop(self):
        self.running = False


class RCSuper(rx.State):
    """Same loop, but the root is a superseding handler (the #7145 trace)."""

    n: int = 0
    limit: int = 3000
    running: bool = False

    @rx.event(supersedes=True)
    async def root(self):
        self.n = 0
        self.running = True
        yield RCSuper.tick

    @rx.event
    async def tick(self):
        if not self.running:
            return
        await asyncio.sleep(0.002)
        self.n += 1
        if self.n < self.limit:
            yield RCSuper.tick

    @rx.event
    def stop(self):
        self.running = False


def recursion_page() -> rx.Component:
    return rx.vstack(
        rx.heading("recursion #7145"),
        rx.text(RC.n, id="rcn"),
        rx.text(rx.cond(RC.finished, "FINISHED", "running"), id="rcstate"),
        rx.button("stop", id="rcstop", on_click=RC.stop),
        rx.text(RCSuper.n, id="rcsn"),
        rx.button("super-root", id="rcsroot", on_click=RCSuper.root),
        rx.button("super-stop", id="rcsstop", on_click=RCSuper.stop),
        rx.link("other page", href="/other", id="toother"),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


def other_page() -> rx.Component:
    return rx.vstack(
        rx.heading("other"),
        rx.text("nothing here", id="otherhere"),
        rx.link("back to recursion", href="/recursion", id="torecursion"),
        rx.link("home", href="/"),
        padding="1em",
    )


# ----------------------------------------------------------------- /callback


class CB(rx.State):
    """Callback routing probe (#7156 / #7157)."""

    events: list[str] = []
    uploaded: list[str] = []

    @rx.event
    def record(self, what: str):
        self.events = [*self.events, what]

    @rx.event
    def clear(self):
        self.events = []
        self.uploaded = []

    @rx.event
    def backend_toast(self):
        """Toast yielded from the backend, with action/cancel on_click."""
        self.events = [*self.events, "be:fired"]
        return rx.toast(
            "backend toast",
            duration=60000,
            action={"label": "BE-Act", "on_click": CB.record("be-action")},
            cancel={"label": "BE-Cancel", "on_click": CB.record("be-cancel")},
        )

    @rx.event
    def backend_toast_upload(self):
        """Backend toast whose action triggers the upload client handler."""
        return rx.toast(
            "backend upload toast",
            duration=60000,
            action={
                "label": "BE-Upload",
                "on_click": CB.handle_upload(rx.upload_files(upload_id="u2")),
            },
        )

    @rx.event
    def script_then_upload(self):
        """call_script whose callback is the uploadFiles client handler (#7156)."""
        return rx.call_script(
            "window.__cb_ran = (window.__cb_ran||0)+1; 'ok'",
            callback=CB.handle_upload(rx.upload_files(upload_id="u2")),
        )

    @rx.event
    def script_then_state(self):
        return rx.call_script("'from-script'", callback=CB.record_script)

    @rx.event
    def record_script(self, value):
        self.events = [*self.events, f"script:{value}"]

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        names = []
        for f in files:
            await f.read()
            names.append(f.name or "?")
        self.uploaded = [*self.uploaded, *names]
        self.events = [*self.events, f"upload:{len(names)}"]


@rx.memo
def memo_toast_button(label: str) -> rx.Component:
    """Toast fired from inside an rx.memo component."""
    return rx.button(
        label,
        id="memotoast",
        on_click=rx.toast(
            "memo toast",
            duration=60000,
            action={"label": "Memo-Act", "on_click": CB.record("memo-action")},
            cancel={"label": "Memo-Cancel", "on_click": CB.record("memo-cancel")},
        ),
    )


class ToastCS(rx.ComponentState):
    """Toast fired from inside a ComponentState."""

    hits: int = 0

    @rx.event
    def hit(self):
        self.hits += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        return rx.hstack(
            rx.button(
                "cs-toast",
                id="cstoast",
                on_click=rx.toast(
                    "component state toast",
                    duration=60000,
                    action={"label": "CS-Act", "on_click": cls.hit},
                    cancel={"label": "CS-Cancel", "on_click": rx.set_clipboard("cs")},
                ),
            ),
            rx.text(cls.hits, id="cshits"),
        )


cs_toast = ToastCS.create()


def callback_page() -> rx.Component:
    return rx.vstack(
        rx.heading("callbacks #7156/#7157"),
        rx.hstack(
            rx.button(
                "fe-toast",
                id="fetoast",
                on_click=rx.toast(
                    "frontend toast",
                    duration=60000,
                    action={"label": "FE-Act", "on_click": CB.record("fe-action")},
                    cancel={"label": "FE-Cancel", "on_click": CB.record("fe-cancel")},
                ),
            ),
            rx.button(
                "fe-toast-js",
                id="fetoastjs",
                on_click=rx.toast(
                    "frontend toast js",
                    duration=60000,
                    action={
                        "label": "FE-JS",
                        "on_click": rx.set_clipboard("clip-from-toast"),
                    },
                    cancel={
                        "label": "FE-Alert",
                        "on_click": rx.call_script("window.__alerted = true"),
                    },
                ),
            ),
            rx.button(
                "fe-toast-upload",
                id="fetoastupload",
                on_click=rx.toast(
                    "frontend upload toast",
                    duration=60000,
                    action={
                        "label": "FE-Upload",
                        "on_click": CB.handle_upload(rx.upload_files(upload_id="u2")),
                    },
                ),
            ),
            rx.button("be-toast", id="betoast", on_click=CB.backend_toast),
            rx.button(
                "be-toast-upload", id="betoastupload", on_click=CB.backend_toast_upload
            ),
        ),
        rx.hstack(
            rx.button("script->upload", id="scriptupload", on_click=CB.script_then_upload),
            rx.button("script->state", id="scriptstate", on_click=CB.script_then_state),
            memo_toast_button(label="memo-toast"),
            cs_toast,
            rx.button("clear", id="cbclear", on_click=CB.clear),
        ),
        rx.upload(
            rx.text("deferred zone u2 (no on_drop)"),
            id="u2",
            border="1px dashed blue",
            padding="0.5em",
        ),
        rx.upload(
            rx.text("drop zone"),
            id="u1",
            on_drop=CB.handle_upload(rx.upload_files(upload_id="u1")),
            border="1px dashed gray",
            padding="0.5em",
        ),
        rx.text(CB.events.to_string(), id="cbevents", font_family="monospace"),
        rx.text(CB.uploaded.to_string(), id="cbuploaded", font_family="monospace"),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


# ----------------------------------------------------------------- /filtered


class FL(rx.State):
    """Uncached var whose delta entry is dropped by a downstream get_delta filter."""

    n: int = 0
    visible: bool = False
    drops: int = 0

    @rx.var(cache=False)
    def secret(self) -> str:
        return f"secret-{self.n}"

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def make_visible(self):
        self.visible = True

    @rx.event
    def hide(self):
        self.visible = False


_orig_get_delta = rx.state.BaseState.get_delta


def _filtered_get_delta(self):
    """Downstream-style delta filter: hide FL.secret while FL.visible is False."""
    delta = _orig_get_delta(self)
    if isinstance(self, FL) and not self.visible:
        state_delta = delta.get(FL.get_full_name())
        if state_delta is not None:
            for key in list(state_delta):
                if key.startswith("secret"):
                    del state_delta[key]
            if not state_delta:
                del delta[FL.get_full_name()]
    return delta


rx.state.BaseState.get_delta = _filtered_get_delta  # type: ignore[assignment]


def filtered_page() -> rx.Component:
    return rx.vstack(
        rx.heading("filtered get_delta (handover lead)"),
        rx.text(FL.n, id="fln"),
        rx.text(FL.secret, id="flsecret"),
        rx.text(FL.visible.to_string(), id="flvisible"),
        rx.hstack(
            rx.button("bump", id="flbump", on_click=FL.bump),
            rx.button("show", id="flshow", on_click=FL.make_visible),
            rx.button("hide", id="flhide", on_click=FL.hide),
        ),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("event_loop probe"),
        rx.link("uncached", href="/uncached", id="l-uncached"),
        rx.link("supersede", href="/supersede", id="l-supersede"),
        rx.link("recursion", href="/recursion", id="l-recursion"),
        rx.link("callback", href="/callback", id="l-callback"),
        rx.link("filtered", href="/filtered", id="l-filtered"),
        rx.text("ready", id="ready"),
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(uncached_page, route="/uncached")
app.add_page(supersede_page, route="/supersede")
app.add_page(recursion_page, route="/recursion", on_load=RC.on_load_start)
app.add_page(other_page, route="/other")
app.add_page(callback_page, route="/callback")
app.add_page(filtered_page, route="/filtered")


# ------------------------------------------------- /upbtn (verifier control)


class UB(rx.State):
    """Documented upload-button pattern control."""

    got: list[str] = []

    @rx.event
    async def handle(self, files: list[rx.UploadFile]):
        for f in files:
            await f.read()
            self.got = [*self.got, f.name or "?"]

    @rx.event
    def clear(self):
        self.got = []


def upbtn_page() -> rx.Component:
    """The documented rx.upload + sibling submit button pattern, plus variants."""
    return rx.vstack(
        rx.heading("upload button scopes"),
        rx.upload(
            rx.text("zone u3"),
            id="u3",
            border="1px dashed green",
            padding="0.5em",
        ),
        rx.button(
            "sibling-upload",
            id="upsib",
            on_click=UB.handle(rx.upload_files(upload_id="u3")),
        ),
        rx.upload(
            rx.vstack(
                rx.text("zone u4"),
                rx.button(
                    "inner-upload",
                    id="upinner",
                    on_click=UB.handle(rx.upload_files(upload_id="u4")),
                ),
            ),
            id="u4",
            border="1px dashed purple",
            padding="0.5em",
        ),
        rx.button("clear", id="upclear", on_click=UB.clear),
        rx.text(UB.got.to_string(), id="ubgot", font_family="monospace"),
        rx.link("home", href="/"),
        spacing="1",
        padding="1em",
    )


app.add_page(upbtn_page, route="/upbtn")
