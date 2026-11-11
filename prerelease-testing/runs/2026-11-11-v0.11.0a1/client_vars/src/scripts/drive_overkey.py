"""Drive reflex-examples overkey (ClientStateVar typing app). Usage: drive_overkey.py <base> <label>"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/overkey")
p = r.new_page("A")
p.goto(base)
p.wait_for_function("document.querySelectorAll('#words .letter').length > 50", timeout=60000)
letters = p.evaluate("Array.from(document.querySelectorAll('#words .letter')).slice(0, 40).map(e => e.textContent).join('')")
print("first 40 expected chars:", repr(letters))
n_letters = p.evaluate("document.querySelectorAll('#words .letter').length")
print("letters rendered:", n_letters)
# choose the 5 second limit through the radix select
p.locator("button[role=combobox]").nth(1).click()
p.get_by_role("option", name="5 seconds", exact=True).click()
p.wait_for_function("document.querySelectorAll('#words .letter').length > 20")
time.sleep(0.5)
letters = p.evaluate("Array.from(document.querySelectorAll('#words .letter')).slice(0, 12).map(e => e.textContent).join('')")
n_letters = p.evaluate("document.querySelectorAll('#words .letter').length")
print("after 5s limit, letters rendered:", n_letters, "first 12:", repr(letters))
inp = p.locator("input").first
inp.focus()
t0 = time.time()
typed = letters[:10] + "#"  # 10 correct + 1 wrong
p.keyboard.type(typed, delay=30)
p.wait_for_function("getComputedStyle(document.querySelectorAll('#words .letter')[10]).opacity === '1'", timeout=10000)
t1 = time.time()
st = p.evaluate("Array.from(document.querySelectorAll('#words .letter')).slice(0, 13).map(e => [getComputedStyle(e).opacity, getComputedStyle(e).backgroundColor, e.className])")
r.check("first 10 letters marked typed (opacity 1)", all(s[0] == "1" for s in st[:11]), st[:11])
r.check("11th (wrong) letter highlighted pink", "255, 192, 203" in st[10][1], st[10])
r.check("12th letter is the caret (blink) and untyped", "blink" in st[11][2] and st[11][0] == "0.5", st[11])
print(f"typing {len(typed)} chars took {t1 - t0:.2f}s (30ms/key => {0.03 * len(typed):.2f}s floor)")
# keystroke latency on the full letter grid: 20 more keys, no delay
t0 = time.time()
p.keyboard.type("abcdefghij", delay=0)
p.wait_for_function("getComputedStyle(document.querySelectorAll('#words .letter')[20]).opacity === '1'", timeout=10000)
print(f"10 keys no-delay -> painted in {time.time() - t0:.3f}s")
p.wait_for_function("document.body.innerText.includes(\"Time's up!\")", timeout=15000)
r.check("time is up shown", True)
p.wait_for_function("document.body.innerText.includes('WPM')", timeout=5000)
txt = p.evaluate("Array.from(document.querySelectorAll('div')).map(e => e.innerText).find(t => /^[0-9.]+ WPM/.test(t))")
print("result:", txt)
r.check("WPM/accuracy computed from retrieved client value (10 of 21 correct = 47.62%)", txt is not None and "47.62%" in txt, txt)
p.screenshot(path=f"results/overkey/{label}_timeup.png")
# restart -> input cleared via on_mount=user_input_state.set_value("")
p.locator("button").first.click()
p.wait_for_function("!document.body.innerText.includes(\"Time's up!\")", timeout=10000)
time.sleep(1.0)
st = p.evaluate("Array.from(document.querySelectorAll('#words .letter')).slice(0, 3).map(e => [getComputedStyle(e).opacity, e.className])")
val = p.locator("input").first.input_value()
r.check("after restart: input cleared and letters untyped", val == "" and st[0][0] == "0.5", f"input={val!r} {st}")
fails = r.finish()
sys.exit(1 if fails else 0)
