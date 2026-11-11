"""Drive csapp (client_state). Usage: drive_cs.py <base_url> <label> [outdir]"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
outdir = sys.argv[3] if len(sys.argv) > 3 else "results/cs"
r = Run(base, label, outdir)
p = r.new_page("A")
T = r.expect_text


def rc(page):
    return page.evaluate("Object.assign({}, window.__rc || {})")


def nav(page, link_id, heading):
    page.click(f"#{link_id}")
    page.wait_for_function(f"document.querySelector('h1') && document.querySelector('h1').textContent === {heading!r}", timeout=15000)


# index: named var shared by page readers and the layout header
r.goto(p, "/")
p.fill("#q-input", "hello")
T(p, "#q-a", "hello"); T(p, "#q-b", "hello"); T(p, "#hdr-query", "hello")
T(p, "#pc", "0")
p.click("#pc-inc"); p.click("#pc-inc"); T(p, "#pc", "2", "set(lambda) increments")
p.click("#pc-5"); T(p, "#pc", "5", "set(value)")
p.click("#fv-dbl"); p.click("#fv-dbl"); T(p, "#fv", "4", "set(FunctionVar) updater")
p.click("#chain1"); T(p, "#pc", "15", "chain cs-first: client"); T(p, "#sc", "1", "chain cs-first: server")
p.click("#chain2"); T(p, "#pc", "115", "chain server-first: client"); T(p, "#sc", "2", "chain server-first: server")
p.fill("#suf-input", "abc"); T(p, "#suf", "abc!", "trigger arg compound")
p.click("#sv"); T(p, "#pc", "42", "set_value(42) deprecated path works")
p.fill("#sv-input", "viaSV"); T(p, "#suf", "viaSV", "set_value() bare deprecated path works")
p.fill("#form-field", "from-form"); p.click("#form-submit"); T(p, "#q-a", "from-form", "form on_submit -> named set")
T(p, "#dup-a", "dup-default"); T(p, "#dup-b", "dup-default")
p.click("#dup-set-a"); T(p, "#dup-a", "via-a"); T(p, "#dup-b", "via-a", "same name, two modules share one slot")
p.click("#dup-set-b"); T(p, "#dup-a", "via-b")

# render isolation: write one var, count renders of other readers
time.sleep(0.3)
before = rc(p)
for _ in range(5):
    p.click("#pc-inc")
T(p, "#pc", "47")
time.sleep(0.3)
after = rc(p)
delta = {k: after.get(k, 0) - before.get(k, 0) for k in after}
print("render deltas after 5 writes to page_count:", delta)
r.check("render isolation: writers of pc do not re-render fv/unrelated/static/q_a/hdr readers",
        all(delta.get(k, 0) == 0 for k in ("fv", "unrelated", "static", "q_a", "hdr_query", "sc")) and delta.get("pc", 0) >= 5, delta)
before = rc(p)
p.fill("#q-input", "x"); T(p, "#q-a", "x")
time.sleep(0.3)
after = rc(p)
delta = {k: after.get(k, 0) - before.get(k, 0) for k in after}
print("render deltas after 1 write to named query:", delta)
r.check("render isolation: named write re-renders only its readers",
        all(delta.get(k, 0) == 0 for k in ("fv", "unrelated", "static", "pc", "sc")) and delta.get("q_a", 0) >= 1 and delta.get("hdr_query", 0) >= 1, delta)
before = rc(p)
p.click("#chain1"); T(p, "#sc", "3")
time.sleep(0.3)
after = rc(p)
delta = {k: after.get(k, 0) - before.get(k, 0) for k in after}
print("render deltas after server state change + pc write:", delta)
r.check("server state delta does not re-render client_state readers (except written pc)",
        all(delta.get(k, 0) == 0 for k in ("fv", "unrelated", "static", "q_a", "hdr_query")), delta)

# navigation: page-owned values reset, named persist
p.click("#pl-inc"); p.click("#pl-inc"); T(p, "#pl", "2")
nav(p, "nav-other", "other")
T(p, "#q-other", "x", "named var persists across client navigation"); T(p, "#hdr-query", "x")
T(p, "#pl-other", "0", "module-level unnamed var is per page (other page starts at default)")
T(p, "#dup-other", "via-b", "named dup persists")
p.click("#ol-set"); T(p, "#ol", "changed")
p.click("#pl-inc-other"); T(p, "#pl-other", "1")
p.fill("#q-input-other", "typed-on-other"); T(p, "#hdr-query", "typed-on-other")
nav(p, "nav-home", "index")
T(p, "#q-a", "typed-on-other", "named var written on /other visible on /")
T(p, "#pc", "0", "page-owned unnamed var reset after navigating away and back")
T(p, "#pl", "0", "module-level unnamed var reset on remount")
T(p, "#fv", "1", "fv reset")
nav(p, "nav-other", "other")
T(p, "#ol", "other-default", "other page unnamed var reset on remount")
p.go_back(); p.wait_for_function("document.querySelector('h1').textContent === 'index'")
T(p, "#q-a", "typed-on-other", "named survives history back")
p.reload(); p.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
T(p, "#q-a", "", "named var resets on full reload (client-only, not persisted)")

# memo page
nav(p, "nav-memo", "memo")
p.click("#counter-one .inc"); p.click("#counter-one .inc"); p.click("#counter-two .dec")
T(p, "#counter-one .val", "2", "memo instance one"); T(p, "#counter-two .val", "-1", "memo instance two"); T(p, "#counter-three .val", "0", "memo instance three independent")
p.click("#plain-x .inc"); T(p, "#plain-x .val", "1"); T(p, "#plain-y .val", "0", "plain helper called twice: distinct vars")
rows = p.locator("#memo-rows .memo-row")
r.check("memo foreach rows rendered", rows.count() == 3, rows.count())
rows.nth(1).locator(".tog").click()
states = [rows.nth(i).locator(".st").text_content() for i in range(3)]
r.check("memo rows in foreach: per-row state", states == ["closed", "open", "closed"], states)
lrows = p.locator("#lambda-rows .lambda-row")
lrows.nth(1).locator(".tog").click()
time.sleep(0.3)
lstates = [lrows.nth(i).locator(".st").text_content() for i in range(lrows.count())]
print("plain-lambda foreach rows after toggling row 1:", lstates)
r.check("INFO plain foreach lambda rows share one unnamed var (documented: use @rx.memo for per-row)", lstates in (["open"] * 3, ["closed", "open", "closed"]), lstates)
# list mutations: add row at the end, delete the first
p.click("#add-row"); p.wait_for_function("document.querySelectorAll('#memo-rows .memo-row').length === 4")
states = [rows.nth(i).locator(".st").text_content() for i in range(4)]
r.check("memo rows after append keep state", states == ["closed", "open", "closed", "closed"], states)
p.click("#del-first"); p.wait_for_function("document.querySelectorAll('#memo-rows .memo-row').length === 3")
states = [rows.nth(i).locator(".st").text_content() for i in range(3)]
texts = [rows.nth(i).locator("p").first.text_content() for i in range(3)]
print("memo rows after deleting first item:", texts, states)
r.check("INFO memo rows after deleting first item: state follows index (no key) or item", True, f"{texts} {states}")
# cond branches
T(p, "#cond-a", "A0"); p.click("#set-cond-a"); T(p, "#cond-a", "A1")
p.click("#toggle-branch"); T(p, "#cond-b", "B0"); p.click("#set-cond-b"); T(p, "#cond-b", "B1")
p.click("#toggle-branch"); T(p, "#cond-a", "A1", "cond branch var survives branch unmount (page-owned)")
p.click("#toggle-branch"); T(p, "#cond-b", "B1", "cond branch b survives")
# ComponentState
p.click("#step-1 .linc"); p.click("#step-1 .both")
T(p, "#step-1 .local", "2"); T(p, "#step-1 .server", "1"); T(p, "#step-2 .local", "0", "ComponentState instances have separate client_state"); T(p, "#step-2 .server", "0")
# memo counters read the named var too
p.fill("#q-input", "zz") if p.locator("#q-input").count() else None
r.check("memo counters show named query", p.locator("#counter-one .q").text_content() == p.locator("#hdr-query").text_content(), p.locator("#counter-one .q").text_content())
nav(p, "nav-home", "index"); nav(p, "nav-memo", "memo")
T(p, "#counter-one .val", "0", "memo instance state reset after page remount")
T(p, "#cond-b", "B0", "cond var reset after remount") if p.locator("#cond-b").count() else T(p, "#cond-a", "A0", "cond var reset after remount")

# backend page
nav(p, "nav-backend", "backend")
p.click("#push"); T(p, "#q-backend", "from-backend", "push from handler"); T(p, "#hdr-query", "from-backend")
p.click("#retrieve"); T(p, "#retrieved", "'from-backend'", "retrieve to handler")
p.click("#push-many"); T(p, "#q-backend", "p2", "several pushes in one handler: last wins")
T(p, "#blob", '{"n":7,"items":["x","é","😀"],"nested":{"none":null}}', "push complex value")
p.click("#retrieve-blob"); T(p, "#retrieved", "{'n': 7, 'items': ['x', 'é', '😀'], 'nested': {'none': None}}", "retrieve complex value")
p.click("#retrieve-hidden"); T(p, "#retrieved", "None", "retrieve never-mounted var -> None (default not known to store)")
p.click("#push-hidden"); p.click("#retrieve-hidden"); T(p, "#retrieved", "'secret'", "push+retrieve never-rendered var")
p.click("#clear-log"); T(p, "#rlog", "")
p.click("#bg-push"); T(p, "#bg-status", "bg-push-done", timeout=8000); T(p, "#q-backend", "bg-2", "push from background task")
p.click("#bg-retrieve"); T(p, "#retrieved", "'bg-2'", "retrieve from background task")
p.click("#ptr"); T(p, "#retrieved", "'ordered'", "push then retrieve in one handler is ordered"); T(p, "#q-backend", "ordered")
p.click("#script-set"); T(p, "#q-backend", "from-call-script", "refs.__client_state.set from call_script")
p.click("#str"); T(p, "#retrieved", "'chained'", "client set then server retrieve in one chain")
p.click("#retrieve-late"); T(p, "#retrieved", "None", "retrieve of a var mounted only on another page -> None")
p.click("#push-late")
time.sleep(0.5)
nav(p, "nav-other", "other")
T(p, "#late", "pushed-before-mount", "value pushed before mount is picked up on mount")

# legacy page
nav(p, "nav-legacy", "legacy")
T(p, "#ln", "L0"); p.click("#ln-set"); T(p, "#ln", "L1", "legacy set_value")
p.fill("#ln-input", "typed"); T(p, "#ln", "typed", "legacy .set on_change")
p.click("#ll-inc"); p.click("#ll-inc"); T(p, "#ll", "2", "legacy global_ref=False set_value(value+1)")
p.click("#ln-push"); T(p, "#ln", "L-pushed", "legacy push")
p.click("#ln-retrieve"); T(p, "#ln-got", "L-pushed", "legacy retrieve")
nav(p, "nav-home", "index"); nav(p, "nav-legacy", "legacy")
T(p, "#ln", "L-pushed", "legacy named (global) persists across nav")
T(p, "#ll", "0", "legacy global_ref=False resets on remount (0.10.1: check baseline)")

# second tab: client state is per tab
p2 = r.new_page("B")
r.goto(p2, "/")
T(p2, "#q-a", "", "named var is per tab (not shared across tabs)")
p.screenshot(path=f"{outdir}/{label}_end.png")
fails = r.finish()
sys.exit(1 if fails else 0)
