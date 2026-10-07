"""Drive the enterprise mantine demo (+ the QA page qa_mantine.py added by this cluster).

Usage: drive_mantine.py <base_url> <out_dir> <expected_venv> <label>
"""
import datetime as dt
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)
TODAY = dt.date.today()


def toasts(p):
    return p.locator("[data-sonner-toast]").all_inner_texts()


def wait_toast(p, text, timeout=5000):
    try:
        p.wait_for_function("t => [...document.querySelectorAll('[data-sonner-toast]')].some(e => e.innerText.includes(t))", arg=text, timeout=timeout)
        return True
    except Exception:
        return False


def card(p, title):
    # the card whose first text line is exactly `title`
    return p.locator(".rt-Card").filter(has=p.locator(f"p.rt-Text:text-is('{title}')")).first


def go(p, route):
    p.goto(base + route, wait_until="networkidle")
    p.wait_for_timeout(1500)


def scenario(s, name, fn, *a):
    try:
        fn(*a)
    except Exception:
        s.check(f"{name}: scenario completed", False, traceback.format_exc()[-700:])


def dates(s, p):
    go(p, "/dates")
    s.check("dates: 12 picker cards render", p.locator("[role=tabpanel] .rt-Card").count() == 12, p.locator("[role=tabpanel] .rt-Card").count())
    c = card(p, "DatePicker")
    c.locator("button.mantine-DatePicker-day:not([data-outside])", has_text="15").first.click()
    want = TODAY.replace(day=15).isoformat()
    s.check("dates: DatePicker day click -> on_change toast with ISO date", wait_toast(p, f"Date selected: {want}"), toasts(p))
    card(p, "MonthPicker").locator("button", has_text="Mar").first.click()
    s.check("dates: MonthPicker -> toast 'Month selected: YYYY-03-01'", wait_toast(p, f"Month selected: {TODAY.year}-03-01"), toasts(p))
    card(p, "YearPicker").locator("button", has_text=str(TODAY.year + 1)).first.click()
    s.check("dates: YearPicker -> toast 'Year selected: YYYY-01-01'", wait_toast(p, f"Year selected: {TODAY.year + 1}-01-01"), toasts(p))
    # popover input
    card(p, "DatePickerInput").locator("button, input").first.click()
    p.wait_for_timeout(600)
    p.locator(".mantine-Popover-dropdown button.mantine-DatePickerInput-day:not([data-outside])", has_text="20").first.click()
    want = TODAY.replace(day=20).isoformat()
    s.check("dates: DatePickerInput popover day -> toast and input shows the date", wait_toast(p, f"Date selected: {want}"), {"toasts": toasts(p), "input": card(p, "DatePickerInput").inner_text()})
    # presets
    pc = card(p, "DatePicker w/ presets")
    pc.locator("button", has_text="Tomorrow").first.click()
    want = (TODAY + dt.timedelta(days=1)).isoformat()
    s.check("dates: preset 'Tomorrow' (dayjs Var) -> toast with tomorrow", wait_toast(p, f"Date selected: {want}"), toasts(p))
    # TimeInput
    ti = card(p, "TimeInput").locator("input").first
    s.note(f"TimeInput element: {ti.evaluate('e => e.outerHTML')[:200]}")
    ti.fill("10:30")
    p.keyboard.press("Tab")
    s.check("dates: TimeInput typing -> on_change toast with time", wait_toast(p, "Time selected: 10:30"), toasts(p))
    s.shot(p, "dates")


def pill(s, p):
    go(p, "/pill")
    s.check("pill: 7 pills render", p.locator(".mantine-Pill-root").count() == 7, p.locator(".mantine-Pill-root").count())
    p.locator(".mantine-Pill-remove").first.click()
    s.check("pill: remove button -> on_remove toast 'Removed'", wait_toast(p, "Removed"), toasts(p))


def tags(s, p):
    go(p, "/tags-input")
    labels = lambda: p.locator(".mantine-TagsInput-pill .mantine-Pill-label").all_inner_texts()  # noqa: E731
    s.check("tags-input: initial State.tags rendered", labels() == ["Tag1", "Tag2"], labels())
    inp = p.locator("input.mantine-TagsInput-inputField")
    inp.click()
    inp.type("Tag3")
    inp.press("Enter")
    p.wait_for_timeout(800)
    s.check("tags-input: typing + Enter adds a tag via on_change -> State", labels() == ["Tag1", "Tag2", "Tag3"], labels())
    p.locator(".mantine-TagsInput-pill").first.locator(".mantine-Pill-remove").click()
    p.wait_for_timeout(800)
    s.check("tags-input: pill remove updates State", labels() == ["Tag2", "Tag3"], labels())
    inp.click()
    inp.type("Tag2")
    inp.press("Enter")
    p.wait_for_timeout(800)
    s.check("tags-input: duplicate tag rejected", labels() == ["Tag2", "Tag3"], labels())
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1500)
    s.check("tags-input: tags survive reload (session state)", labels() == ["Tag2", "Tag3"], labels())


def qa(s, p):
    go(p, "/qa-mantine")
    ac = p.locator("#qa-autocomplete")
    ac.click()
    ac.type("Ba")
    p.wait_for_timeout(500)
    p.locator("[role=option]:has-text('Banana')").first.click()
    p.wait_for_timeout(800)
    s.check("qa: Autocomplete on_option_submit -> State", "Banana" in p.locator("#qa-fruit").inner_text(), p.locator("#qa-fruit").inner_text())
    p.keyboard.press("Escape")
    p.locator("#qa-multiselect").focus()
    p.keyboard.press("ArrowDown")
    p.wait_for_timeout(400)
    s.note(f"multiselect dropdown visible options: {p.locator('.mantine-MultiSelect-option:visible').all_inner_texts()}")
    p.locator(".mantine-MultiSelect-option:visible:has-text('Vue')").first.click()
    p.wait_for_timeout(800)
    s.check("qa: MultiSelect on_change -> State list", p.locator("#qa-picks").inner_text().endswith("React,Vue"), p.locator("#qa-picks").inner_text())
    p.keyboard.press("Escape")
    p.click("#qa-bump")
    p.wait_for_timeout(700)
    s.check("qa: RingProgress label follows State (30 -> 50)", "50" in p.locator("#qa-ring-label").inner_text(), p.locator("#qa-ring-label").inner_text())
    sect = p.locator(".mantine-RingProgress-root circle").evaluate_all("els => els.map(e => e.getAttribute('stroke-dasharray'))")
    s.note(f"ring sections stroke-dasharray: {sect}")
    js = p.locator("#qa-json")
    js.fill('{"b": [1,2]}')
    p.locator("#qa-bump").focus()
    p.wait_for_timeout(800)
    s.check("qa: JsonInput on_change -> State and format_on_blur reformats", '"b"' in p.locator("#qa-json-text").inner_text(), {"state": p.locator("#qa-json-text").inner_text(), "input": js.input_value()})
    js.fill("{bad json")
    p.locator("#qa-bump").focus()
    p.wait_for_timeout(600)
    s.check("qa: JsonInput shows validation_error on invalid JSON", p.locator("text=Invalid JSON").count() > 0, p.locator(".mantine-JsonInput-error, .mantine-InputWrapper-error").all_inner_texts())
    vis0 = p.locator("#qa-collapsed").is_visible()
    p.click("#qa-toggle")
    p.wait_for_timeout(800)
    vis1 = p.locator("#qa-collapsed").is_visible()
    s.check("qa: Collapse in_=State.opened toggles content", (not vis0) and vis1, {"before": vis0, "after": vis1})
    s.check("qa: NumberFormatter renders State-derived value", p.locator("text=$ 50,000").count() > 0, p.locator("[role=tabpanel]").first.inner_text()[-200:])
    s.shot(p, "qa-mantine")


with Session(f"mantine-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    ctx = s.new_context("mantine")
    p = s.new_page(ctx, "mantine")
    go(p, "/")
    links = p.locator("[role=tabpanel] a").all_inner_texts()
    s.check("index lists the demo pages", len(links) >= 3, links)
    scenario(s, "dates", dates, s, p)
    scenario(s, "pill", pill, s, p)
    scenario(s, "tags-input", tags, s, p)
    scenario(s, "qa", qa, s, p)
