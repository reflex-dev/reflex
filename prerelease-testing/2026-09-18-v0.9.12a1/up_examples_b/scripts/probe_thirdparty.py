"""Probe the reflex import surface used by reflex-local-auth and reflex-global-hotkey."""
import os, importlib
import reflex
assert os.environ["EXPECT_VENV"] in reflex.__file__, reflex.__file__
print("reflex at", reflex.__file__)
CHECKS = [
    ("reflex.event", ["EventSpec", "EventHandler", "EventType", "key_event", "KeyInputInfo"]),
    ("reflex", ["Fragment", "Var", "State", "LocalStorage", "Cookie", "session", "var", "event",
                "input", "form", "set_value", "set_focus", "redirect", "cond", "foreach", "memo"]),
    ("reflex.utils", ["imports"]),
]
bad = []
for mod, names in CHECKS:
    m = importlib.import_module(mod)
    for n in names:
        try:
            getattr(m, n)
        except Exception as e:
            bad.append(f"{mod}.{n}: {type(e).__name__}: {e}")
from reflex.utils import imports as _imp
for n in ("ImportVar", "ImportDict", "merge_imports"):
    if not hasattr(_imp, n):
        bad.append(f"reflex.utils.imports.{n}: MISSING")
print("MISSING:", bad or "none")
import reflex_local_auth, reflex_global_hotkey
print("reflex_local_auth OK:", reflex_local_auth.LocalAuthState, reflex_local_auth.LoginState, reflex_local_auth.RegistrationState)
print("reflex_global_hotkey OK:", reflex_global_hotkey.global_hotkey_watcher)
