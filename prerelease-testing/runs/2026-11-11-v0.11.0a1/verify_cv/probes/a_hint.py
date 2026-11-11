"""Item A: follow the client_state 'give it a name' hint literally."""
import sys

import reflex as rx

assert "/envs/vcv-new/" in rx.__file__, rx.__file__

def hook_of(v):
    return list(v._get_all_var_data().hooks)

# 1. unnamed var -> push raises the hint
v = rx.client_state("x")
try:
    v.push(1)
except ValueError as e:
    print("unnamed push:", e)

# 2. follow the hint verbatim
hinted = rx.client_state("my_name")
print("hinted _is_global:", hinted._is_global, "state_name:", hinted._state_name, "hooks:", hook_of(hinted))
try:
    hinted.push(1)
    print("hinted push: OK")
except ValueError as e:
    print("hinted push: SAME ERROR ->", str(e)[:60])

# 3. docstring line
doc = rx.ClientStateVar.create.__doc__
print("docstring:", [l.strip() for l in doc.splitlines() if "my_name" in l])

# 4. correct call
ok = rx.client_state("", name="my_name")
print("correct _is_global:", ok._is_global, hook_of(ok))
ok.push(1); print("correct push OK")

# 5. migration trap: rx.ClientStateVar is the NEW class
for call in ['rx.ClientStateVar.create("user_input", default="")', 'rx.ClientStateVar.create("user_input")', 'rx.client_state("user_input", "")']:
    try:
        r = eval(call)
        print(call, "->", "global" if r._is_global else "UNNAMED/scoped", "default js:", hook_of(r))
    except TypeError as e:
        print(call, "-> TypeError:", e)
