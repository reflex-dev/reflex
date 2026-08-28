"""Verify a2 deprecation shims work at runtime (FINDING-008/009 + item 10)."""
import warnings, reflex, sys
assert "envs/" in reflex.__file__ and "site-packages" in reflex.__file__, reflex.__file__
print("reflex.__file__:", reflex.__file__)
import reflex as rx

def probe(label, fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            r = fn()
            print(f"OK    {label}: -> {type(r).__name__} {str(r)[:60]!r}")
        except Exception as e:
            print(f"CRASH {label}: {type(e).__name__}: {e}")
            return
        # deprecation-ish message?
        msgs = [str(x.message) for x in w]
        print(f"      warnings({len(msgs)}): {msgs[:2]}")

# 1. bundled_libraries shim
probe("dynamic.bundled_libraries", lambda: __import__('reflex.components.dynamic', fromlist=['bundled_libraries']).bundled_libraries)
# 2. DEFAULT_BUNDLED_LIBRARIES shim
probe("dynamic.DEFAULT_BUNDLED_LIBRARIES", lambda: getattr(__import__('reflex.components.dynamic', fromlist=['x']), 'DEFAULT_BUNDLED_LIBRARIES'))
# 3. DECORATED_PAGES shim
def get_dp():
    from reflex.page import DECORATED_PAGES
    return DECORATED_PAGES
probe("reflex.page.DECORATED_PAGES", get_dp)
# 4. get_config(reload=True)
probe("get_config(reload=True)", lambda: rx.config.get_config(reload=True))
