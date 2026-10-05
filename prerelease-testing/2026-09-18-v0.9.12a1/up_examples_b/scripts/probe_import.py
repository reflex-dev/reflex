"""Import each example app module under the venv running this script."""
import os, sys, traceback
import reflex
VENV = os.environ.get("EXPECT_VENV", "")
assert VENV in reflex.__file__, f"WRONG REFLEX: {reflex.__file__}"
print("reflex:", reflex.__file__)
APPS = {
    "form-designer": "form_designer",
    "twitter": "twitter",
    "basic_crud": "basic_crud",
    "reflexle": "reflexle",
    "data_visualisation": "data_visualisation",
}
root = os.path.dirname(os.path.abspath(__file__))
for d, mod in APPS.items():
    appdir = os.path.join(root, d)
    sys.path.insert(0, appdir)
    olddir = os.getcwd()
    os.chdir(appdir)
    try:
        from reflex_base.utils import registration  # noqa
    except Exception:
        registration = None
    try:
        import importlib
        m = importlib.import_module(f"{mod}.{mod}")
        print(f"OK   {d}: {m}")
    except Exception as e:
        print(f"FAIL {d}: {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        os.chdir(olddir)
        sys.path.remove(appdir)
    # purge modules so next app starts clean-ish
    for k in list(sys.modules):
        if k.split(".")[0] in APPS.values():
            del sys.modules[k]
