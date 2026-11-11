"""Drive varsapp /unicode (#7548). Usage: drive_unicode.py <base> <label>"""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/unicode")
p = r.new_page("A")
r.goto(p, "/unicode")
table = {}


def cps(s):
    return " ".join(f"{ord(c):X}" for c in s)


def snapshot(name):
    time.sleep(0.4)
    exp = json.loads(p.locator("#u_expected").text_content())
    got = {
        "reversed": p.locator("#u_reversed").text_content(),
        "length": p.locator("#u_length").text_content(),
        "chars": json.dumps(p.eval_on_selector_all("#u-each .c", "els => els.map(e => e.textContent)"), ensure_ascii=False),
        "slice_0_2": p.locator("#u_slice_0_2").text_content(),
        "slice_1_": p.locator("#u_slice_1_").text_content(),
        "slice_neg": p.locator("#u_slice_neg").text_content(),
        "at_1": p.locator("#u_at_1").text_content(),
        "at_last": p.locator("#u_at_last").text_content(),
        "upper": p.locator("#u_upper").text_content(),
        "lower": p.locator("#u_lower").text_content(),
        "contains_emoji": p.locator("#u_contains_emoji").text_content(),
    }
    diffs = {}
    for k, g in got.items():
        e = exp[k]
        if k in ("chars",):
            same = json.loads(g) == json.loads(e)
        else:
            same = g == e
        if not same:
            diffs[k] = {"frontend": f"{g!r} [{cps(g)}]", "python": f"{e!r} [{cps(e)}]"}
    # .split() / .split("") are not part of #7548: record whether they yield code points (like foreach) or UTF-16 units
    split_default = json.loads(p.locator("#u_split_none").text_content())
    split_is_codepoints = split_default == json.loads(exp["chars"])
    r.check(f"[{name}] INFO StringVar.split() yields code points like rx.foreach", True, f"code_points={split_is_codepoints} parts={len(split_default)} vs chars={len(json.loads(exp['chars']))}")
    table[name] = {"split_is_codepoints": split_is_codepoints,"s": p.locator("#u_s").text_content(), "codepoints": exp["codepoints"], "got": got, "split_empty": p.locator("#u_split_empty").text_content(), "diffs": diffs}
    r.check(f"[{name}] string ops equal Python (code points)", not diffs, diffs if diffs else f"len={got['length']} reversed={got['reversed']!r} chars={got['chars']}")


snapshot("default a😀b")
for k in ("ascii", "emoji", "family", "flag", "combining", "skin", "cjk", "empty"):
    p.click(f"#pick-{k}")
    time.sleep(0.2)
    snapshot(k)
    if k in ("family", "flag", "combining", "skin"):
        p.locator("#u-each").screenshot(path=f"results/unicode/{label}_{k}_each.png") if p.locator("#u-each .c").count() else None
# typed by the user (IME-like input of an astral char + combining mark)
p.fill("#u-input", "x𝒳ýz")
snapshot("typed x𝒳ýz")
p.screenshot(path=f"results/unicode/{label}_page.png")
print(json.dumps({k: {"s": v["s"], "cp": v["codepoints"], "len": v["got"]["length"], "reversed": v["got"]["reversed"], "chars": v["got"]["chars"], "split_empty": v["split_empty"]} for k, v in table.items()}, indent=1, ensure_ascii=False))
with open(f"results/unicode/{label}_table.json", "w") as f:
    json.dump(table, f, indent=1, ensure_ascii=False)
fails = r.finish()
sys.exit(1 if fails else 0)
