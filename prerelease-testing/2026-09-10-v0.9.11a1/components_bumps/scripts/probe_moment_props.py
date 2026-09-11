"""Probe how rx.moment handles props react-moment 2.x dropped or never wrapped.

Run from this directory with the alpha venv:
    $SB/envs/compbumps/bin/python probe_moment_props.py
"""

import reflex as rx

assert "/envs/compbumps/" in rx.__file__, rx.__file__


def show(label, **props):
    """Render a moment with the given props and print what came out."""
    try:
        c = rx.moment("2024-03-14T00:00:00", **props)
        rendered = c.render()
        print(f"{label}: OK props={rendered['props']}")
    except Exception as e:  # noqa: BLE001
        print(f"{label}: {type(e).__name__}: {e}")


show("filter (dropped in react-moment 2.x)", filter="uppercase")
show("calendar (react-moment prop, not wrapped)", calendar=True)
show("settings (react-moment 2.x global config prop)", settings={"locale": "fr"})
show("typo: form_at", form_at="YYYY")
show("supported: format", format="YYYY")
