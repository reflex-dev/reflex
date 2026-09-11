"""rx.moment exercised against react-moment 2.0.2."""

import datetime

import reflex as rx


class MomentState(rx.State):
    """State for the moment page."""

    iso_date: str = "2024-03-14T15:09:26"
    dt: datetime.datetime = datetime.datetime(2024, 3, 14, 15, 9, 26)
    unix_ts: int = 1710428966
    change_count: int = 0
    last_change: str = ""
    dates: list[str] = [
        "2020-01-01T00:00:00",
        "2021-06-15T12:30:00",
        "2022-12-25T18:45:00",
    ]
    tz_name: str = "America/New_York"
    locale_name: str = "fr"

    @rx.event
    def on_change(self, value: str):
        """Record an on_change from rx.moment.

        Args:
            value: The new rendered value.
        """
        self.change_count += 1
        self.last_change = str(value)

    @rx.event
    def bump_date(self):
        """Move the state date forward by one day."""
        self.dt = self.dt + datetime.timedelta(days=1)
        self.iso_date = self.dt.isoformat()

    @rx.event
    def next_tz(self):
        """Rotate the timezone used by the tz probe."""
        zones = ["America/New_York", "Asia/Tokyo", "Europe/Paris", "UTC"]
        self.tz_name = zones[(zones.index(self.tz_name) + 1) % len(zones)]

    @rx.event
    def next_locale(self):
        """Rotate the locale used by the locale probe."""
        locales = ["fr", "es", "de", "en"]
        self.locale_name = locales[(locales.index(self.locale_name) + 1) % len(locales)]


@rx.memo
def memo_moment(date: rx.Var[str]) -> rx.Component:
    """A moment inside an rx.memo component.

    Args:
        date: The date to render.

    Returns:
        The component.
    """
    return rx.moment(date, format="YYYY-MM-DD HH:mm", id="m-memo")


class MomentCS(rx.ComponentState):
    """A ComponentState wrapping a moment."""

    offset: int = 0

    @rx.event
    def add_day(self):
        """Add a day to the offset."""
        self.offset += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        """Build the component.

        Args:
            props: Extra props.

        Returns:
            The component.
        """
        return rx.hstack(
            rx.moment(
                "2024-03-14T00:00:00",
                add=rx.MomentDelta(days=cls.offset),
                format="YYYY-MM-DD",
                id=props.pop("id", "m-cstate"),
            ),
            rx.button("cs +1d", on_click=cls.add_day, id="m-cstate-btn"),
            **props,
        )


client_date = rx._x.client_state("moment_client_date", default="2019-07-04T08:00:00")


def row(label: str, comp: rx.Component) -> rx.Component:
    """A labelled row.

    Args:
        label: The label text.
        comp: The component to show.

    Returns:
        The row component.
    """
    return rx.hstack(
        rx.text(label, width="20em", size="1", color_scheme="gray"),
        comp,
        align="center",
        spacing="2",
    )


def moment_page() -> rx.Component:
    """The moment page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("moment (react-moment 2.0.2)", size="4"),
        rx.link("home", href="/"),
        client_date,
        row("static + format", rx.moment("2024-03-14T15:09:26", format="YYYY-MM-DD HH:mm:ss", id="m-static")),
        row("state str date", rx.moment(MomentState.iso_date, format="YYYY-MM-DD HH:mm:ss", id="m-state-str")),
        row("state datetime date", rx.moment(MomentState.dt, format="YYYY-MM-DD HH:mm:ss", id="m-state-dt")),
        row("date= as child", rx.moment(date=MomentState.iso_date, format="MMM D, YYYY", id="m-date-prop")),
        row("client_state date", rx.moment(client_date.value, format="YYYY-MM-DD", id="m-client")),
        rx.hstack(
            rx.button("bump state date", on_click=MomentState.bump_date, id="m-bump"),
            rx.button(
                "bump client date",
                on_click=client_date.set_value("2021-11-11T11:11:11"),
                id="m-client-bump",
            ),
        ),
        row("from_now", rx.moment("2020-01-01T00:00:00", from_now=True, id="m-fromnow")),
        row("from_now_short", rx.moment("2020-01-01T00:00:00", from_now=True, from_now_short=True, id="m-fromnow-short")),
        row("to_now", rx.moment("2020-01-01T00:00:00", to_now=True, id="m-tonow")),
        row(
            "from_now_during (huge)",
            rx.moment(
                "2020-01-01T00:00:00",
                from_now_during=10**13,
                format="YYYY-MM-DD",
                id="m-fnd-relative",
            ),
        ),
        row(
            "from_now_during (tiny)",
            rx.moment(
                "2020-01-01T00:00:00",
                from_now_during=1000,
                format="YYYY-MM-DD",
                id="m-fnd-absolute",
            ),
        ),
        row(
            "duration + trim",
            rx.moment(
                date="2026-08-30T00:30:00",
                duration="2026-08-30T00:00:00",
                format="h [hrs] m [min]",
                trim=True,
                id="m-duration",
            ),
        ),
        row(
            "duration hh:mm:ss",
            rx.moment(
                date="2026-08-30T02:03:04",
                duration="2026-08-30T00:00:00",
                format="hh:mm:ss",
                id="m-duration-fmt",
            ),
        ),
        row(
            "duration trim=False",
            rx.moment(
                date="2026-08-30T00:00:30",
                duration="2026-08-30T00:00:00",
                format="d [d] h [h] m [m] s [s]",
                trim=False,
                id="m-duration-notrim",
            ),
        ),
        row(
            "duration_from_now",
            rx.moment("2020-01-01T00:00:00", duration_from_now=True, format="y [years]", id="m-durfromnow"),
        ),
        row("unix", rx.moment(MomentState.unix_ts, unix=True, format="YYYY-MM-DD HH:mm:ss", id="m-unix")),
        row("tz NY", rx.moment("2024-03-14T15:09:26Z", tz="America/New_York", format="YYYY-MM-DD HH:mm z", id="m-tz-ny")),
        row("tz Tokyo", rx.moment("2024-03-14T15:09:26Z", tz="Asia/Tokyo", format="YYYY-MM-DD HH:mm z", id="m-tz-tokyo")),
        row("tz Paris", rx.moment("2024-03-14T15:09:26Z", tz="Europe/Paris", format="YYYY-MM-DD HH:mm z", id="m-tz-paris")),
        row("tz from state", rx.moment("2024-03-14T15:09:26Z", tz=MomentState.tz_name, format="HH:mm z", id="m-tz-state")),
        rx.button("next tz", on_click=MomentState.next_tz, id="m-tz-btn"),
        row("locale fr", rx.moment("2024-03-14T15:09:26", locale="fr", format="dddd D MMMM YYYY", id="m-locale-fr")),
        row("locale es", rx.moment("2024-03-14T15:09:26", locale="es", format="dddd D MMMM YYYY", id="m-locale-es")),
        row("locale from state", rx.moment("2024-03-14T15:09:26", locale=MomentState.locale_name, format="dddd D MMMM", id="m-locale-state")),
        rx.button("next locale", on_click=MomentState.next_locale, id="m-locale-btn"),
        row("interval 1000 + on_change", rx.moment(interval=1000, format="HH:mm:ss", on_change=MomentState.on_change, id="m-interval")),
        row("interval 0 (static now)", rx.moment(interval=0, format="HH:mm:ss", id="m-interval0")),
        rx.text("on_change count: ", rx.text.strong(MomentState.change_count, id="m-change-count")),
        rx.text("last change: ", rx.text.strong(MomentState.last_change, id="m-last-change")),
        row("add 3 days", rx.moment("2024-03-14T00:00:00", add=rx.MomentDelta(days=3), format="YYYY-MM-DD", id="m-add")),
        row(
            "subtract 2 months 1 hour",
            rx.moment(
                "2024-03-14T05:00:00",
                subtract=rx.MomentDelta(months=2, hours=1),
                format="YYYY-MM-DD HH:mm",
                id="m-sub",
            ),
        ),
        row("parse list", rx.moment("14/03/2024", parse="DD/MM/YYYY", format="YYYY-MM-DD", id="m-parse-list")),
        row("parse str", rx.moment("14-03-2024", parse="DD-MM-YYYY", format="YYYY-MM-DD", id="m-parse-str")),
        row("with_title", rx.moment("2024-03-14T15:09:26", with_title=True, title_format="YYYY/MM/DD", format="MMM D", id="m-title")),
        row("diff + unit", rx.moment("2024-03-14T00:00:00", diff="2024-03-01T00:00:00", unit="days", id="m-diff")),
        row("diff decimal", rx.moment("2024-03-14T12:00:00", diff="2024-03-01T00:00:00", unit="days", decimal=True, id="m-diff-dec")),
        row("local", rx.moment("2024-03-14T15:09:26Z", local=True, format="YYYY-MM-DD HH:mm", id="m-local")),
        rx.text("foreach:"),
        rx.vstack(
            rx.foreach(
                MomentState.dates,
                lambda d, i: rx.hstack(
                    rx.text(f"#", size="1"),
                    rx.moment(d, format="YYYY-MM-DD", id=f"m-foreach-{i}"),
                ),
            ),
            id="m-foreach",
        ),
        rx.text("memo:"),
        memo_moment(date=MomentState.iso_date),
        rx.text("component state:"),
        MomentCS.create(id="m-cstate"),
        spacing="2",
        padding="1em",
        align="start",
    )
