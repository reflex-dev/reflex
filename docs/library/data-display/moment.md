---
components:
  - rx.moment
---

# Moment

Displaying date and relative time to now sometimes can be more complicated than necessary.

To make it easy, Reflex is wrapping [react-moment](https://www.npmjs.com/package/react-moment) under `rx.moment`.

```python exec
import reflex as rx
from reflex.utils.serializers import serialize_datetime
```

## Examples

Using a date from a state var as a value, we will display it in a few different
way using `rx.moment`.

The `date_now` state var is initialized when the site was deployed. The
button below can be used to update the var to the current datetime, which will
be reflected in the subsequent examples.

```python demo exec
from datetime import datetime, timezone


class MomentState(rx.State):
    date_now: datetime = datetime.now(timezone.utc)

    @rx.event
    def update(self):
        self.date_now = datetime.now(timezone.utc)


def moment_update_example():
    return rx.button(
        "Update", rx.moment(MomentState.date_now), on_click=MomentState.update
    )
```

```python test
def test_moment_update_button_refreshes_date(demo):
    from datetime import datetime, timedelta

    def shown():
        return datetime.strptime(time.inner_text(), "%a %b %d %Y %H:%M:%S GMT%z")

    button = demo.get_by_role("button", name=re.compile("^Update"))
    time = button.locator("time")
    before = time.inner_text()
    stale = datetime.now().astimezone() - shown() > timedelta(seconds=2)
    button.click()
    if stale:
        expect(time).not_to_have_text(before)
    # The button now shows the current time.
    assert abs(datetime.now().astimezone() - shown()) < timedelta(seconds=10)
```

### Display the date as-is:

```python demo
rx.moment(MomentState.date_now)
```

```python test
def test_moment_default_format(demo):
    expect(demo.locator("time")).to_have_text(
        re.compile(r"^\w{3} \w{3} \d{2} \d{4} \d{2}:\d{2}:\d{2} GMT[+-]\d{4}$")
    )
```

### Humanized interval

Sometimes we don't want to display just a raw date, but we want something more instinctive to read. That's when we can use `from_now` and `to_now`.

```python demo
rx.moment(MomentState.date_now, from_now=True)
```

```python test
def test_moment_from_now(page, demo):
    page.get_by_role("button", name=re.compile("^Update")).click()
    expect(demo.locator("time")).to_have_text("a few seconds ago")
```

```python demo
rx.moment(MomentState.date_now, to_now=True)
```

```python test
def test_moment_to_now(page, demo):
    page.get_by_role("button", name=re.compile("^Update")).click()
    expect(demo.locator("time")).to_have_text("in a few seconds")
```

You can also set a duration (in milliseconds) with `from_now_during` where the date will display as relative, then after that, it will be displayed as defined in `format`.

```python demo
rx.moment(
    MomentState.date_now, from_now_during=100000
)  # after 100 seconds, date will display normally
```

```python test
def test_moment_from_now_during(page, demo):
    # Recently updated, the date is still within the relative window.
    page.get_by_role("button", name=re.compile("^Update")).click()
    expect(demo.locator("time")).to_have_text("a few seconds ago")
```

### Formatting dates

```python demo
rx.moment(MomentState.date_now, format="YYYY-MM-DD")
```

```python test
def test_moment_date_format(demo):
    expect(demo.locator("time")).to_have_text(re.compile(r"^\d{4}-\d{2}-\d{2}$"))
```

```python demo
rx.moment(MomentState.date_now, format="HH:mm:ss")
```

```python test
def test_moment_time_format(demo):
    expect(demo.locator("time")).to_have_text(re.compile(r"^\d{2}:\d{2}:\d{2}$"))
```

### Offset Date

With the props `add` and `subtract`, you can pass an `rx.MomentDelta` object to modify the displayed date without affecting the stored date in your state.

#### Add

```python demo
rx.vstack(
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(years=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(quarters=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(months=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(weeks=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now, add=rx.MomentDelta(days=2), format="YYYY-MM-DD - HH:mm:ss"
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(hours=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(minutes=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        add=rx.MomentDelta(seconds=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
)
```

```python test
def test_moment_add_offsets(demo):
    from datetime import datetime, timedelta

    times = demo.locator("time")
    expect(times).to_have_text(
        [re.compile(r"^\d{4}-\d{2}-\d{2} - \d{2}:\d{2}:\d{2}$")] * 8
    )
    parsed = [
        datetime.strptime(text, "%Y-%m-%d - %H:%M:%S")
        for text in times.all_inner_texts()
    ]
    years, _, _, weeks, days, _, minutes, seconds = parsed
    base = seconds - timedelta(seconds=2)
    assert years.year == base.year + 2
    assert weeks - base == timedelta(weeks=2)
    assert days - base == timedelta(days=2)
    assert minutes - base == timedelta(minutes=2)
```

#### Subtract

```python demo
rx.vstack(
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(years=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(quarters=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(months=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(weeks=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(days=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(hours=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(minutes=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
    rx.moment(
        MomentState.date_now,
        subtract=rx.MomentDelta(seconds=2),
        format="YYYY-MM-DD - HH:mm:ss",
    ),
)
```

```python test
def test_moment_subtract_offsets(demo):
    from datetime import datetime, timedelta

    times = demo.locator("time")
    expect(times).to_have_text(
        [re.compile(r"^\d{4}-\d{2}-\d{2} - \d{2}:\d{2}:\d{2}$")] * 8
    )
    parsed = [
        datetime.strptime(text, "%Y-%m-%d - %H:%M:%S")
        for text in times.all_inner_texts()
    ]
    years, _, _, weeks, days, _, minutes, seconds = parsed
    base = seconds + timedelta(seconds=2)
    assert years.year == base.year - 2
    assert base - weeks == timedelta(weeks=2)
    assert base - days == timedelta(days=2)
    assert base - minutes == timedelta(minutes=2)
```

### Locales

Each `rx.moment` defaults to English. Set `locale` on a component to render it
in another language; other components and pages keep their own locale.

```python demo
rx.vstack(
    rx.moment(MomentState.date_now, format="dddd D MMMM YYYY"),
    rx.moment(MomentState.date_now, format="dddd D MMMM YYYY", locale="fr"),
)
```

```python test
def test_moment_locales(demo):
    english, french = demo.locator("time").all()
    expect(english).to_have_text(
        re.compile(
            r"^(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day \d{1,2} [A-Z][a-z]+ \d{4}$"
        )
    )
    expect(french).to_have_text(
        re.compile(
            r"^(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche) \d{1,2} \w+ \d{4}$"
        )
    )
```

### Shared defaults

Wrap components in `rx.moment_provider` to give them a shared `locale`,
`format`, `timezone`, `local`, `parse`, `element`, `filters`, or `renderers`
default. A prop set on a component overrides the provider. Components outside
the provider keep English. Set `pool=True` to update all descendants from one
timer that ticks every `interval` milliseconds.

```python demo exec
def moment_provider_example():
    return rx.moment_provider(
        rx.moment("2024-03-14"),
        rx.moment("2024-03-14", locale="en"),
        locale="fr",
        format="D MMM YYYY",
        timezone="Europe/Paris",
    )
```

```python test
def test_moment_provider_defaults(demo):
    expect(demo.locator("time")).to_have_text(["14 mars 2024", "14 Mar 2024"])
```

### Additional react-moment 2.x options

`rx.moment` also supports the `utc`, `calendar`, `from_`, `to`, `ago`, `element`,
`fallback`, `filters`, and `renderers` options from `react-moment` 2.x. In Python,
`from_` maps to the JavaScript `from` prop. `filters` and `renderers` accept
JavaScript function values:

```python
rx.moment(
    "2024-03-14",
    format="MMMM",
    filters=[rx.Var("(content) => content.toUpperCase()")],
)
```

### Timezones

You can also set dates to display in a specific timezone:

```python demo
rx.vstack(
    rx.moment(MomentState.date_now, tz="America/Los_Angeles"),
    rx.moment(MomentState.date_now, tz="Europe/Paris"),
    rx.moment(MomentState.date_now, tz="Asia/Tokyo"),
)
```

```python test
def test_moment_timezones(demo):
    times = demo.locator("time")
    expect(times).to_have_text(
        [re.compile(r"^\w{3} \w{3} \d{2} \d{4} \d{2}:\d{2}:\d{2} GMT[+-]\d{4}$")] * 3
    )
    # Los Angeles, Paris and Tokyo each show a different local time.
    assert len(set(times.all_inner_texts())) == 3
```

### Client-side periodic update

If a date is not passed to `rx.moment`, it will use the client's current time.

If you want to update the date every second, you can use the `interval` prop.

```python demo
rx.moment(interval=1000, format="HH:mm:ss")
```

```python test
def test_moment_interval_ticks(demo):
    time = demo.locator("time")
    expect(time).to_have_text(re.compile(r"^\d{2}:\d{2}:\d{2}$"))
    expect(time).not_to_have_text(time.inner_text())
```

The `on_change` event fires when the component mounts and whenever the date is updated.
Starting with `reflex-components-moment` 0.9.4, this includes static dates and
`interval=0`: disabling periodic updates does not suppress the initial event.
It fires again when the component remounts, such as after a reload or route navigation.
React Strict Mode can invoke the mount event twice in development, so handlers with
side effects should account for repeated calls.

Connect an event handler with the `on_change` prop:

```python demo exec
class MomentLiveState(rx.State):
    updating: bool = False

    @rx.event
    def on_update(self, date):
        return rx.toast(f"Date updated: {date}")

    @rx.event
    def set_updating(self, value: bool):
        self.updating = value


def moment_live_example():
    return rx.hstack(
        rx.moment(
            format="HH:mm:ss",
            interval=rx.cond(MomentLiveState.updating, 5000, 0),
            on_change=MomentLiveState.on_update,
        ),
        rx.switch(
            is_checked=MomentLiveState.updating,
            on_change=MomentLiveState.set_updating,
        ),
    )
```

```python test
def test_moment_on_change_and_live_switch(page, demo):
    time = demo.locator("time")
    before = time.inner_text()
    switch = demo.get_by_role("switch")
    switch.click()
    expect(switch).to_be_checked()
    # Every 5 second tick updates the time and fires on_change.
    expect(time).not_to_have_text(before, timeout=10000)
    expect(page.get_by_text(re.compile(r"^Date updated: ")).first).to_be_visible()
```
