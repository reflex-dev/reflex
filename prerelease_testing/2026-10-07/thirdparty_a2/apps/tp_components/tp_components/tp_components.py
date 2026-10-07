"""Third-party component sweep: one page per package, identical source for 0.9.12 and 0.10.0a1.

Every page body is built inside `guard()`, so a package that fails while building its
component shows the error on its own page (id=page_error) instead of breaking the app.
"""

from __future__ import annotations

import traceback
from typing import Any

import reflex as rx

ERRORS: dict[str, str] = {}
PAGES: list[str] = []
PAGE_FNS: dict[str, Any] = {}


def guard(route: str, build):
    PAGES.append(route)

    def page() -> rx.Component:
        try:
            body = build()
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"
            ERRORS[route] = msg + "\n" + traceback.format_exc()[-2500:]
            print(f"[tp_components] page {route} failed to build: {msg}", flush=True)  # noqa: T201
            body = rx.el.pre(msg, id="page_error")
        return rx.vstack(rx.link("home", href="/"), rx.heading(route, id="page_title"), body)

    page.__name__ = "page_" + route.strip("/").replace("-", "_")
    rx.page(route=route)(page)
    PAGE_FNS[route] = page
    return page


# reflex-global-hotkey
from reflex_global_hotkey import global_hotkey_watcher  # noqa: E402
from reflex.event import KeyInputInfo  # noqa: E402


class HotkeyState(rx.State):
    keys: list[str] = []

    @rx.event
    def on_key(self, key: str, info: KeyInputInfo):
        mods = "+".join(m for m in ("alt", "ctrl", "meta", "shift") if info.get(f"{m}_key"))
        self.keys.append(f"{mods + '+' if mods else ''}{key}")


guard("/hotkey", lambda: rx.vstack(
    global_hotkey_watcher(on_key_down=HotkeyState.on_key),
    rx.text(HotkeyState.keys.join(","), id="keys"),
))

# reflex-intersection-observer
from reflex_intersection_observer import IntersectionObserverEntry, intersection_observer  # noqa: E402


class IOState(rx.State):
    seen: int = 0
    unseen: int = 0
    ratio: float = 0.0

    @rx.event
    def on_seen(self, entry: IntersectionObserverEntry):
        self.seen += 1
        ratio = entry.get("intersection_ratio", 0) if isinstance(entry, dict) else getattr(entry, "intersection_ratio", 0)
        self.ratio = float(ratio or 0)

    @rx.event
    def on_unseen(self, entry: IntersectionObserverEntry):
        self.unseen += 1


guard("/intersection", lambda: rx.vstack(
    rx.text("seen=", IOState.seen, " unseen=", IOState.unseen, id="io_counts", position="fixed", top="0", right="0"),
    rx.box(height="2000px", id="spacer"),
    intersection_observer(rx.text("TARGET", id="io_target"), on_intersect=IOState.on_seen, on_non_intersect=IOState.on_unseen, threshold=0.5),
    rx.box(height="500px"),
))

# reflex-audio-capture
from reflex_audio_capture import AudioRecorderPolyfill, get_codec  # noqa: E402


class AudioState(rx.State):
    chunks: int = 0
    total: int = 0
    codec: str = ""
    error: str = ""
    started: bool = False

    @rx.event
    def on_data(self, data: str):
        self.chunks += 1
        self.total += len(data)
        self.codec = get_codec(data)

    @rx.event
    def on_error(self, err: dict):
        self.error = str(err)[:200]

    @rx.event
    def on_start(self):
        self.started = True


def _audio():
    capture = AudioRecorderPolyfill.create(
        id="tp_audio",
        on_data_available=AudioState.on_data,
        on_start=AudioState.on_start,
        on_error=AudioState.on_error,
        timeslice=500,
    )
    return rx.vstack(
        capture,
        rx.button("Start Recording", id="rec_start", on_click=capture.start()),
        rx.button("Stop Recording", id="rec_stop", on_click=capture.stop()),
        rx.text("chunks=", AudioState.chunks, " total=", AudioState.total, " codec=", AudioState.codec, " started=", AudioState.started.to_string(), " error=", AudioState.error, id="audio_status"),
    )


guard("/audio", _audio)

# reflex-webcam
from reflex_webcam import upload_screenshot, webcam  # noqa: E402


class CamState(rx.State):
    shot_len: int = 0
    prefix: str = ""

    @rx.event
    def on_shot(self, data: str):
        self.shot_len = len(data or "")
        self.prefix = (data or "")[:22]


guard("/webcam", lambda: rx.vstack(
    webcam(id="tp_cam", width="320px", height="240px"),
    rx.button("Snap", id="snap", on_click=upload_screenshot("tp_cam", CamState.on_shot)),
    rx.text("len=", CamState.shot_len, " prefix=", CamState.prefix, id="cam_status"),
))

# reflex-simpleicons
from reflex_simpleicons import simpleicons  # noqa: E402

guard("/icons", lambda: rx.hstack(
    rx.box(simpleicons("github"), id="icon_github"),
    rx.box(simpleicons("python", brand_color=True), id="icon_python"),
    rx.box(simpleicons("docker", color="red", size=32), id="icon_docker"),
))

# reflex-monaco
from reflex_monaco import monaco  # noqa: E402


class MonacoState(rx.State):
    code: str = "print('hello')"

    @rx.event
    def set_code(self, value: str):
        self.code = value


guard("/monaco", lambda: rx.vstack(
    monaco(default_value=MonacoState.code, language="python", height="200px", width="600px", on_change=MonacoState.set_code.debounce(100)),
    rx.text(MonacoState.code, id="monaco_code"),
))

# reflex-calendar
from reflex_calendar import calendar  # noqa: E402


class CalState(rx.State):
    picked: str = ""

    @rx.event
    def on_change(self, date: str):
        self.picked = str(date)


guard("/calendar", lambda: rx.vstack(
    calendar(on_change=CalState.on_change),
    rx.text("picked=", CalState.picked, id="cal_picked"),
))

# reflex-pyplot
import matplotlib  # noqa: E402

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402
from reflex_pyplot import pyplot  # noqa: E402


class PlotState(rx.State):
    n: int = 3

    @rx.var
    def fig(self) -> Figure:
        f = Figure(figsize=(3, 2))
        ax = f.add_subplot()
        ax.plot(list(range(self.n)), [i * i for i in range(self.n)])
        return f

    @rx.event
    def more(self):
        self.n += 2


guard("/pyplot", lambda: rx.vstack(
    pyplot(PlotState.fig, id="plot_img", width="300px"),
    rx.button("more", id="plot_more", on_click=PlotState.more),
    rx.text("n=", PlotState.n, id="plot_n"),
))

# reflex-google-recaptcha-v2 (Google's public test keys)
import reflex_google_recaptcha_v2 as recaptcha  # noqa: E402

recaptcha.set_site_key("6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI")
recaptcha.set_secret_key("6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe")

guard("/recaptcha", lambda: rx.vstack(
    recaptcha.google_recaptcha_v2(id="tp_captcha"),
    rx.text("valid=", recaptcha.GoogleRecaptchaV2State.token_is_valid.to_string(), id="captcha_valid"),
))

# reflex-motion
from reflex_motion import motion  # noqa: E402

guard("/motion", lambda: motion(
    rx.text("MOTION", id="motion_text"),
    initial={"opacity": 0, "x": -50},
    animate={"opacity": 1, "x": 0},
    while_hover={"scale": 1.5},
    transition={"duration": 0.3},
    id="motion_div",
))

# reflex-type-animation
from reflex_type_animation import type_animation  # noqa: E402

guard("/type-animation", lambda: rx.box(
    type_animation(sequence=["Hello from type animation", 500, "Second line"], speed=80, repeat=0, wrapper="span"),
    id="typed",
))

# reflex-image-zoom
from reflex_image_zoom import image_zoom  # noqa: E402

guard("/image-zoom", lambda: image_zoom(rx.image(src="/zoomme.png", width="150px", id="zoom_img", alt="zoomable")))

# reflex-color-picker (module is rx_color_picker)
from rx_color_picker.color_picker import color_picker  # noqa: E402


class ColorState(rx.State):
    color: str = "#aabbcc"

    @rx.event
    def set_color(self, value: str):
        self.color = value


guard("/color-picker", lambda: rx.vstack(
    color_picker(color=ColorState.color, on_change=ColorState.set_color, id="picker"),
    rx.text(ColorState.color, id="color_value"),
))

# reflex-qrcode
from reflex_qrcode import QRCode  # noqa: E402


class QRState(rx.State):
    text: str = "https://reflex.dev"

    @rx.event
    def set_text(self, value: str):
        self.text = value


guard("/qrcode", lambda: rx.vstack(
    rx.input(value=QRState.text, on_change=QRState.set_text, id="qr_input"),
    rx.box(QRCode(value=QRState.text, size=128), id="qr_box"),
))

# reflex-dynoselect
from reflex_dynoselect import dynoselect  # noqa: E402


class DynoState(rx.State):
    picked: str = ""

    @rx.event
    def on_select(self, option: dict):
        self.picked = str(option.get("value", option))


guard("/dynoselect", lambda: rx.vstack(
    dynoselect(
        options=[{"label": "Apple", "value": "apple"}, {"label": "Banana", "value": "banana"}, {"label": "Cherry", "value": "cherry"}],
        placeholder="Pick a fruit",
        search_placeholder="Search fruit",
        on_select=DynoState.on_select,
    ),
    rx.text("picked=", DynoState.picked, id="dyno_picked"),
))

# reflex-chat
import reflex_chat  # noqa: E402

guard("/chat", lambda: rx.box(reflex_chat.chat(), height="500px", width="600px"))
guard("/chat-initial", lambda: rx.box(
    reflex_chat.chat(initial_messages=[{"role": "assistant", "content": "INITIAL-GREETING"}]),
    height="500px", width="600px",
))

# reflex-clerk (needs authlib, which its wheel does not declare)
import reflex_clerk as clerk  # noqa: E402


class ClerkProbe(rx.State):
    report: str = ""

    @rx.event
    def probe(self):
        cs = clerk.ClerkState
        try:
            sk = cs.secret_key
        except Exception as e:  # noqa: BLE001
            sk = f"<{type(e).__name__}: {e}>"
        self.report = (
            f"secret_key={sk!r} _jwt_public_keys={type(cs._jwt_public_keys).__name__} "
            f"_clerk_api_client={type(cs._clerk_api_client).__name__} _fetch_user={cs._fetch_user!r}"
        )


def _clerk():
    return clerk.clerk_provider(
        rx.vstack(
            clerk.signed_out(rx.text("SIGNED-OUT", id="clerk_signed_out")),
            clerk.signed_in(rx.text("SIGNED-IN", id="clerk_signed_in")),
            rx.button("probe ClerkState", id="clerk_probe", on_click=ClerkProbe.probe),
            rx.button("set_clerk_session(bogus)", id="clerk_set_session", on_click=clerk.ClerkState.set_clerk_session("not-a-jwt")),
            rx.text(ClerkProbe.report, id="clerk_report"),
            rx.text("is_signed_in=", clerk.ClerkState.is_signed_in.to_string(), id="clerk_flag"),
        ),
        publishable_key="pk_test_ZHVtbXktY2xlcmsuZXhhbXBsZS5jb20k",
        secret_key="sk_test_dummy_secret",
    )


guard("/clerk", _clerk)


@rx.page(route="/")
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("tp_components"),
        *[rx.link(p, href=p) for p in PAGES],
        rx.link("errors", href="/errors"),
    )


@rx.page(route="/errors")
def errors() -> rx.Component:
    return rx.vstack(*[rx.el.pre(f"{k}: {v}", class_name="err") for k, v in ERRORS.items()], rx.text(f"{len(ERRORS)} errors", id="n_errors"))


app = rx.App()
