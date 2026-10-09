"""reflex-dynoselect 0.1.0: dynotimezone() does `component.State._raw_options = options` on a declared backend var.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_dynoselect.py"""
import os
import traceback

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

import reflex_dynoselect as ds  # noqa: E402

print(f"reflex {version('reflex')} reflex-dynoselect {version('reflex-dynoselect')}")
# the wheel ships no option archives (packaging bug on every version): stub the loader to reach the class-level write
import sys  # noqa: E402

dsm = sys.modules["reflex_dynoselect.dynoselect"]  # the package re-exports a function under the module name

dsm.LocalizedOptions.load = staticmethod(lambda path, locale: [{"value": "Europe/Paris", "label": "Paris"}])
for fn_name in ("dynotimezone", "dynolanguage"):
    try:
        comp = getattr(ds, fn_name)(locale="en")
        st = comp.State
        inst = rx.State(_reflex_internal_init=True).get_substate(st.get_full_name().split(".")[1:])
        raw = getattr(inst, "_raw_options", None)
        print(f"{fn_name}(): created; instance _raw_options len={len(raw) if raw is not None else None}; class attr type={type(st.__dict__.get('_raw_options')).__name__}")
        try:
            inst.refresh()
            print(f"   refresh() -> {len(inst.options)} options, first={inst.options[0].label if inst.options else None}")
        except Exception as e:  # noqa: BLE001
            print(f"   refresh() EXC {type(e).__name__}: {str(e)[:120]}")
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)
        print(f"{fn_name}(): EXC {type(e).__name__}: {str(e)[:200]} @ {[f'{os.path.basename(t.filename)}:{t.lineno}' for t in tb[-2:]]}")
