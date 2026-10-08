"""Import every third-party reflex package and record errors/warnings.

Usage: <venv>/bin/python import_sweep.py <expected-venv-name>
"""
import importlib
import io
import json
import sys
import traceback
import warnings

EXPECTED = sys.argv[1]
import reflex

assert f"/scratchpad/envs/{EXPECTED}/" in reflex.__file__, reflex.__file__

MODS = [
    "reflex_local_auth", "reflex_global_hotkey", "reflex_google_auth",
    "reflex_magic_link_auth", "reflex_intersection_observer", "reflex_audio_capture",
    "reflex_webcam", "reflex_simpleicons", "reflex_monaco", "reflex_calendar",
    "reflex_pyplot", "reflex_chakra", "reflex_ag_grid", "reflex_google_recaptcha_v2",
    "reflex_clerk", "reflex_motion", "reflex_type_animation", "reflex_image_zoom",
    "reflex_dynoselect", "rx_color_picker", "reflex_qrcode", "reflex_chat",
]
results = {}
for m in MODS:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            importlib.import_module(m)
            status = "ok"
            err = None
        except BaseException as e:  # noqa: BLE001
            status = "error"
            err = "".join(traceback.format_exception(e))[-3000:]
    results[m] = {
        "status": status,
        "error": err,
        "warnings": sorted({f"{x.category.__name__}: {x.message} ({x.filename.split('site-packages/')[-1]}:{x.lineno})" for x in w}),
    }
print(json.dumps({"reflex": reflex.__version__ if hasattr(reflex, '__version__') else None, "results": results}, indent=1))
