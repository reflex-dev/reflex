"""Drive stapp with three tabs. Usage: drive_storage.py <base> <label>
Prints an observation table (JSON) so two versions can be diffed, plus checks for #7637 / #7652."""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/storage")
obs = {}
IDS = ["plain", "typed", "ck", "ck30", "ck_path", "ck_typed", "ss", "num", "a", "b", "c", "d", "solo", "unnamed_sync", "mixed_sync", "mixed_nosync", "solo_len", "a_upper"]
SYNC = ["a", "b", "c", "d", "solo", "unnamed_sync", "mixed_sync", "mixed_nosync", "solo_len", "a_upper"]


def vals(p, ids=IDS):
    return {i: p.locator(f"#{i}").text_content() for i in ids}


def ls(p):
    return p.evaluate("Object.fromEntries(Object.entries(localStorage).filter(([k]) => !['theme', 'last_compiled_theme'].includes(k)))")


def setv(p, name, value):
    p.fill("#val", value)
    p.click(f"#set-{name}")


def settle(t=0.9):
    time.sleep(t)


def snap(tag, tabs, ids=SYNC):
    settle()
    obs[tag] = {name: vals(p, ids) for name, p in tabs.items()}
    obs[tag]["localStorage"] = ls(next(iter(tabs.values())))
    return obs[tag]


A = r.new_page("A"); r.goto(A, "/")
obs["00 fresh A values"] = vals(A)
obs["00 fresh A storage"] = {"localStorage": ls(A), "sessionStorage": A.evaluate("Object.fromEntries(Object.entries(sessionStorage).filter(([k]) => k !== 'token'))"), "cookies": sorted(c["name"] for c in r.ctx.cookies())}
obs["00 types"] = A.locator("#types").text_content()
r.check("fresh profile: nothing written to browser storage", obs["00 fresh A storage"] == {"localStorage": {}, "sessionStorage": {}, "cookies": []}, obs["00 fresh A storage"])
B = r.new_page("B"); r.goto(B, "/")
C = r.new_page("C"); r.goto(C, "/")
tabs = {"A": A, "B": B, "C": C}

# #7637: write one of several vars sharing a storage name
setv(A, "a", "A1")
o = snap("01 A sets a=A1", tabs)
r.check("#7637 writing tab: b/c/d follow a (shared name)", [o["A"][k] for k in "abcd"] == ["A1"] * 4, {k: o["A"][k] for k in "abcd"})
r.check("other tabs: a/b/c/d all follow", all([o[t][k] for k in "abcd"] == ["A1"] * 4 for t in "BC"), {t: {k: o[t][k] for k in "abcd"} for t in "BC"})
r.check("computed var over the synced var follows in every tab", all(o[t]["a_upper"] == "A1" for t in "ABC"), {t: o[t]["a_upper"] for t in "ABC"})
B.click("#set-d") if False else None
B.fill("#val", "D2"); B.click("#set-d")
o = snap("02 B sets d=D2 (other state)", tabs)
r.check("#7637 write through a var of another state class propagates to a/b/c in all tabs", all([o[t][k] for k in "abcd"] == ["D2"] * 4 for t in "ABC"), {t: {k: o[t][k] for k in "abcd"} for t in "ABC"})
C.fill("#val", "C3"); C.click("#set-c")
o = snap("03 C sets c=C3 (substate)", tabs)
r.check("#7637 write through a substate var propagates", all([o[t][k] for k in "abcd"] == ["C3"] * 4 for t in "ABC"), {t: {k: o[t][k] for k in "abcd"} for t in "ABC"})
A.click("#set-both")
o = snap("04 A sets a and b to different values in one event", tabs)
r.check("INFO conflicting writes in one event converge on one value everywhere", len({o[t][k] for t in "ABC" for k in "abcd"}) == 1, {t: {k: o[t][k] for k in "abcd"} for t in "ABC"})
C.click("#bg-set-a")
o = snap("05 C background task sets a", tabs, SYNC)
r.check("#7637 background-task write propagates to same-name vars in the writing tab", [o["C"][k] for k in "abcd"] == ["bg-A"] * 4, {k: o["C"][k] for k in "abcd"})
r.check("... and to the other tabs", all([o[t][k] for k in "abcd"] == ["bg-A"] * 4 for t in "AB"), {t: {k: o[t][k] for k in "abcd"} for t in "AB"})
setv(A, "mixed_sync", "M1")
o = snap("06 A sets mixed_sync (same name as a sync=False var)", tabs)
setv(B, "mixed_nosync", "M2")
o = snap("07 B sets mixed_nosync", tabs)
setv(A, "solo", "solo-1")
o = snap("08 A sets solo", tabs)
r.check("plain sync var reaches other tabs", all(o[t]["solo"] == "solo-1" and o[t]["solo_len"] == "6" for t in "ABC"), {t: (o[t]["solo"], o[t]["solo_len"]) for t in "ABC"})
setv(A, "unnamed_sync", "us-1")
o = snap("08b A sets unnamed_sync", tabs)
r.check("sync var without an explicit name reaches other tabs", all(o[t]["unnamed_sync"] == "us-1" for t in "ABC"), {t: o[t]["unnamed_sync"] for t in "ABC"})
setv(A, "plain", "plain-1"); setv(A, "typed", "typed-1"); A.click("#set-num")
settle()
obs["09 non-sync writes"] = {t: vals(p, ["plain", "typed", "num"]) for t, p in tabs.items()}

# #7652: localStorage.clear() in one tab
A.evaluate("localStorage.clear()")
o = snap("10 localStorage.clear() run in tab A (devtools-style)", tabs)
want = {"a": "a-default", "b": "b-default", "c": "c-default", "d": "d-default", "solo": "solo-default", "unnamed_sync": "us-default", "mixed_sync": "ms-default"}
r.check("#7652 other tabs reset synced vars to their defaults", all({k: o[t][k] for k in want} == want for t in "BC"), {t: {k: o[t][k] for k in want} for t in "BC"})
r.check("#7652 computed var over a cleared synced var recomputes (solo_len=12)", all(o[t]["solo_len"] == "12" for t in "BC"), {t: o[t]["solo_len"] for t in "BC"})
obs["10 tab A after its own clear"] = {k: o["A"][k] for k in want}
obs["10 localStorage after clear"] = o["localStorage"]
setv(B, "a", "after-clear")
o = snap("11 B sets a after the clear", tabs)
r.check("sync works again after a clear", all([o[t][k] for k in "abcd"] == ["after-clear"] * 4 for t in "ABC"), {t: {k: o[t][k] for k in "abcd"} for t in "ABC"})
setv(B, "solo", "solo-2"); settle()
B.evaluate("localStorage.removeItem('solo')")
o = snap("12 removeItem('solo') run in tab B", tabs)
r.check("#7652 removeItem: other tabs reset that var to its default", all(o[t]["solo"] == "solo-default" and o[t]["solo_len"] == "12" for t in "AC"), {t: (o[t]["solo"], o[t]["solo_len"]) for t in "AC"})
obs["12 tab B after its own removeItem"] = {"solo": o["B"]["solo"]}
# removal through the reflex events
setv(A, "solo", "solo-3"); settle()
A.click("#remove-solo")
o = snap("13 rx.remove_local_storage('solo') from tab A", tabs)
r.check("rx.remove_local_storage: other tabs reset to default (HYD-12)", all(o[t]["solo"] == "solo-default" and o[t]["solo_len"] == "12" for t in "BC"), {t: (o[t]["solo"], o[t]["solo_len"]) for t in "BC"})
obs["13 tab A after rx.remove_local_storage"] = {"solo": o["A"]["solo"], "solo_len": o["A"]["solo_len"]}
obs["13 localStorage"] = o["localStorage"]
A.click("#remove-shared")
o = snap("14 rx.remove_local_storage('shared') from tab A", tabs)
r.check("rx.remove_local_storage of a shared name: other tabs reset every var to its own default",
        all({k: o[t][k] for k in "abcd"} == {"a": "a-default", "b": "b-default", "c": "c-default", "d": "d-default"} for t in "BC"), {t: {k: o[t][k] for k in "abcd"} for t in "BC"})
setv(B, "a", "x1"); setv(B, "solo", "s1"); settle()
A.click("#clear-ls")
o = snap("15 rx.clear_local_storage() from tab A", tabs)
r.check("rx.clear_local_storage: other tabs reset", all({k: o[t][k] for k in want} == want for t in "BC"), {t: {k: o[t][k] for k in want} for t in "BC"})
obs["15 tab A after rx.clear_local_storage"] = {k: o["A"][k] for k in want}
obs["15 localStorage after rx.clear_local_storage"] = o["localStorage"]
# every tab still works
for t, p in tabs.items():
    before = int(p.locator("#n-events").text_content()); p.click("#bump")
    try:
        p.wait_for_function(f"parseInt(document.querySelector('#n-events').textContent) > {before}", timeout=5000); ok = True
    except Exception:  # noqa: BLE001
        ok = False
    r.check(f"tab {t} still processes events after the clears", ok)
A.reload(); A.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
obs["16 A after reload"] = vals(A)

# session storage is per tab; cookies
setv(A, "ss", "ss-A"); settle()
obs["17 sessionStorage"] = {"A": vals(A, ["ss"]), "B": vals(B, ["ss"])}
setv(A, "ck_typed", "ckt-1"); setv(A, "ck_path", "ckp-1"); setv(A, "ck30", "ck30-1"); setv(A, "ck", "ck-1"); A.wait_for_function("document.querySelector('#ck').textContent === 'ck-1'"); time.sleep(0.3)
now = time.time()
obs["18 raw cookie expiry minus now"] = {c["name"]: round(c.get("expires", -1) - now, 2) for c in r.ctx.cookies() if c.get("expires", -1) > 0}
obs["18 document.cookie names"] = sorted(x.split("=")[0].strip() for x in A.evaluate("document.cookie").split(";") if x.strip())
cookies = {c["name"]: {"value": c["value"], "path": c["path"], "ttl": round(c["expires"] - now) if c.get("expires", -1) > 0 else None, "sameSite": c.get("sameSite")} for c in r.ctx.cookies()}
obs["18 cookies after set"] = cookies
r.check("Cookie max_age=5 -> expires in ~5 s", "ck" in cookies and cookies["ck"]["ttl"] is not None and 2 <= cookies["ck"]["ttl"] <= 6, cookies.get("ck"))
r.check("Cookie max_age=30 -> expires in ~30 s", "ck30" in cookies and cookies["ck30"]["ttl"] is not None and 25 <= cookies["ck30"]["ttl"] <= 31, cookies.get("ck30"))
r.check("Cookie path='/sub' stored with that path", cookies.get("ck_path", {}).get("path") == "/sub", cookies.get("ck_path"))
B.reload(); B.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
obs["19 B reload on / (cookie values)"] = vals(B, ["ck", "ck30", "ck_path", "ck_typed"])
r.goto(B, "/sub")
obs["19 B on /sub (cookie values)"] = vals(B, ["ck", "ck_path", "ck_typed"])
time.sleep(6)
B.reload(); B.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
obs["20 B reload after 6 s (max_age=5 cookie)"] = vals(B, ["ck", "ck_path", "ck_typed"])
print(json.dumps(obs, indent=1))
with open(f"results/storage/{label}_obs.json", "w") as f:
    json.dump(obs, f, indent=1)
fails = r.finish()
sys.exit(1 if fails else 0)
