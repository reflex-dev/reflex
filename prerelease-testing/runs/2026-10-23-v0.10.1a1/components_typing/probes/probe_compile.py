"""Compile-time probes for the 0.10.1a1 component changes (no server needed).

Run with EXPECT_VENV=new (0.10.1a1) and EXPECT_VENV=components_typing-prev (0.10.0):

    EXPECT_VENV=new $SB/envs/new/bin/python probes/probe_compile.py > results/probe_compile_new.json

Every row is {"name", "ok"/"info", "detail"}; rows never raise, exceptions are recorded.
"""

import dataclasses
import json
import os
import sys
import traceback
import warnings

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

rows: list[dict] = []


def row(name, fn):
    try:
        res = fn()
        rows.append({"name": name, "ok": True, "detail": res})
    except Exception as e:  # noqa: BLE001
        rows.append(
            {
                "name": name,
                "ok": False,
                "detail": f"{type(e).__name__}: {e}",
                "tb": traceback.format_exc()[-1500:],
            }
        )


def rendered(c):
    """Return the rendered props of a component (strings)."""
    r = c.render()
    return {"props": r.get("props", []), "name": r.get("name")}


def props_str(c):
    return " ".join(rendered(c)["props"])


class S(rx.State):
    vals: list[str] = []
    flag: bool = False
    ac: str = "email"
    cols: list[dict] = [{"title": "A"}]
    titles: list[str] = ["X", "Y"]
    data: list[list] = [["a", 1]]
    loc: str = "fr"
    name: str = "apple"

    @rx.event
    def set_vals(self, v: list[str]):
        self.vals = v


# ---- radix #7345 checkbox_group / checkbox_cards
def cg_controlled():
    c = rx.checkbox_group.root(
        rx.checkbox_group.item("A", value="a", required=True),
        value=S.vals,
        on_value_change=S.set_vals,
        disabled=True,
        required=True,
        orientation="horizontal",
        dir="rtl",
        loop=True,
        name="g",
    )
    p = props_str(c)
    return {
        "props": rendered(c)["props"],
        "has_value_binding": "value:" in p and "vals" in p,
        "has_onValueChange": "onValueChange" in p,
        "disabled_as_prop": "disabled:true" in p.replace(" ", ""),
        "disabled_in_css": "css:" in p and "disabled" in p.split("css:")[1] if "css:" in p else False,
        "form_control": getattr(type(c), "_is_form_control", None),
    }


row("cg_controlled", cg_controlled)


def cc_controlled():
    c = rx.checkbox_cards.root(
        rx.checkbox_cards.item(rx.text("X"), value="x", disabled=True, required=True),
        value=S.vals,
        on_value_change=S.set_vals,
        default_value=["x"],
        name="cards",
        disabled=False,
        required=True,
        orientation="vertical",
        dir="ltr",
        loop=False,
        columns="2",
    )
    p = props_str(c)
    item_p = props_str(c.children[0])
    return {
        "props": rendered(c)["props"],
        "item_props": rendered(c.children[0])["props"],
        "has_onValueChange": "onValueChange" in p,
        "item_value_prop": "value:" in item_p and "css" not in item_p,
        "form_control": getattr(type(c), "_is_form_control", None),
    }


row("cc_controlled", cc_controlled)


# ---- radix #7593 radio_cards as_child
def rc_aschild():
    c = rx.radio_cards.root(
        rx.radio_cards.item(rx.text("1"), value="1", as_child=True),
        rx.radio_cards.item(rx.text("2"), value="2"),
        as_child=True,
        default_value="1",
    )
    p = props_str(c)
    ip = props_str(c.children[0])
    return {
        "root_props": rendered(c)["props"],
        "item_props": rendered(c.children[0])["props"],
        "root_asChild_prop": "asChild" in p,
        "root_as_child_in_css": "css:" in p and "as" in p.split("css:")[1].lower(),
        "item_asChild_prop": "asChild" in ip,
    }


row("rc_aschild", rc_aschild)


# ---- radix #7418 input auto_complete
def ac_cases():
    out = {}
    for label, val in [
        ("off", "off"),
        ("email", "email"),
        ("true", True),
        ("false", False),
        ("boolvar", S.flag),
        ("strvar", S.ac),
    ]:
        try:
            c = rx.input(auto_complete=val)
            p = [x for x in rendered(c)["props"] if "autoComplete" in x or "css" in x]
            out[label] = p
        except Exception as e:  # noqa: BLE001
            out[label] = f"{type(e).__name__}: {e}"
    c = rx.el.input(auto_complete="off")
    out["el_off"] = [x for x in rendered(c)["props"] if "autoComplete" in x]
    return out


row("ac_cases", ac_cases)


# ---- radix #7438 primitive progress
def prim_progress():
    from reflex_components_radix.primitives.progress import progress

    c = progress(value=S.name.length(), max=200)
    root = rendered(c)
    ind = rendered(c.children[0])
    return {
        "root_tag": root["name"],
        "root_props": root["props"],
        "indicator_props": ind["props"],
        "root_has_value": any(p.startswith("value:") for p in root["props"]),
        "root_has_max": any(p.startswith("max:") for p in root["props"]),
        "library": type(c).__dict__.get("library") or type(c).library,
    }


row("prim_progress", prim_progress)


# ---- radix #7629 accordion :first-of-type
def accordion_style():
    item = rx.accordion.item(header="h", content="c", value="v")
    style = json.dumps(item.add_style() or {}, default=str)
    return {
        "first_of_type": ":first-of-type" in style,
        "first_child": ":first-child" in style,
        "library": rx.accordion.root(item).library,
    }


row("accordion_style", accordion_style)


# ---- #7645 radix primitive versions
def radix_versions():
    from reflex_components_radix.primitives import accordion, dialog, drawer, form, progress, slider

    return {
        "accordion": accordion.AccordionComponent.library,
        "dialog": dialog.DialogElement.library,
        "drawer_deps": drawer.DrawerComponent.lib_dependencies,
        "form": form.FormComponent.library,
        "progress": progress.ProgressComponent.library,
        "slider": slider.SliderComponent.library,
    }


row("radix_versions", radix_versions)


# ---- rx.form namespace / FormData (#7386 radix side)
def form_ns():
    out = {
        "FormData": repr(getattr(rx.form, "FormData", None)),
        "form_call": type(rx.form(rx.input(name="x"))).__name__,
        "form_root": type(rx.form.root(rx.input(name="x"))).__name__,
        "stub_as_class": getattr(type(rx.form), "_stub_as_class", None),
    }
    if hasattr(rx.form, "FormData"):
        out["subscript"] = repr(rx.form.FormData[str, str])
    return out


row("form_ns", form_ns)


# ---- moment #7591
def moment_props():
    out = {}
    cases = {
        "utc": dict(utc=True),
        "calendar": dict(calendar=True),
        "calendar_dict": dict(calendar={"sameDay": "[Today]"}),
        "from_": dict(from_="2024-03-10"),
        "to": dict(to="2024-03-20"),
        "ago": dict(ago=True, from_now=True),
        "element": dict(element="span"),
        "fallback": dict(fallback="x"),
        "filters": dict(filters=[rx.Var("(c) => c")]),
        "renderers": dict(renderers=[rx.Var("(p, d) => null")]),
        "locale_fr": dict(locale="fr"),
        "locale_en": dict(locale="en"),
        "locale_var": dict(locale=S.loc),
        "tz": dict(tz="Europe/Paris"),
    }
    for label, kw in cases.items():
        try:
            c = rx.moment("2024-03-14", **kw)
            ps = rendered(c)["props"]
            css = [p for p in ps if p.startswith("css:")]
            imports = {k: [str(v) for v in vs] for k, vs in c._get_all_imports().items()}
            out[label] = {
                "props": ps,
                "css": css,
                "imports": imports,
                "custom_code": sorted(c._get_all_custom_code()),
            }
        except Exception as e:  # noqa: BLE001
            out[label] = f"{type(e).__name__}: {e}"
    for bad in ("filter", "settings", "form_at"):
        try:
            c = rx.moment("2024-03-14", **{bad: True})
            out[f"bad_{bad}"] = rendered(c)["props"]
        except Exception as e:  # noqa: BLE001
            out[f"bad_{bad}"] = f"{type(e).__name__}: {e}"
    return out


row("moment_props", moment_props)


def moment_provider():
    if not hasattr(rx, "moment_provider"):
        return "n/a (no rx.moment_provider)"
    out = {}
    for label, kw in {
        "fr": dict(locale="fr", format="D MMM YYYY", timezone="Europe/Paris"),
        "en": dict(locale="en"),
        "var": dict(locale=S.loc),
        "pool": dict(pool=True, interval=1000, element="span", filters=[rx.Var("(c)=>c")], renderers=[rx.Var("(p,d)=>null")], local=True, parse="YYYY"),
    }.items():
        c = rx.moment_provider(rx.moment("2024-03-14"), **kw)
        out[label] = {
            "props": rendered(c)["props"],
            "imports": {k: [str(v) for v in vs] for k, vs in c._get_all_imports().items()},
            "custom_code": sorted(c._get_all_custom_code()),
        }
    out["default_locale_field"] = repr(rx.moment("2024-03-14").locale)
    return out


row("moment_provider", moment_provider)


# ---- data_editor #7607
def de_literal_not_mutated():
    cols = [{"title": "Name"}, {"title": "Age", "type": "int"}, {"title": "Birth", "id": "date"}, "Plain"]
    before = json.dumps(cols)
    c = rx.data_editor(columns=cols, data=[["a", 1, "b", "p"]])
    after = json.dumps(cols)
    grid = c.children[0]
    p = [x for x in rendered(grid)["props"] if x.startswith("columns:")]
    return {"mutated": before != after, "before": before, "after": after, "columns_prop": p}


row("de_literal_not_mutated", de_literal_not_mutated)


def de_state_columns():
    out = {}
    for label, kw in {
        "dict_cols": dict(columns=S.cols, data=S.data),
        "title_cols": dict(columns=S.titles, data=S.data),
        "sliced_data": dict(columns=S.cols, data=S.data[1:]),
        "literal_with_var_col": dict(columns=["A", S.cols[0]], data=S.data),
    }.items():
        try:
            c = rx.data_editor(**kw)
            grid = c.children[0]
            hooks = list(grid._get_all_hooks())
            ps = rendered(grid)["props"]
            out[label] = {
                "columns_prop": [x for x in ps if x.startswith("columns:")],
                "getCellContent": [x for x in ps if x.startswith("getCellContent:")],
                "hooks": hooks,
                "react_imports": sorted(str(i.tag) for i in grid._get_all_imports().get("react", [])),
            }
        except Exception as e:  # noqa: BLE001
            out[label] = f"{type(e).__name__}: {e}"
    return out


row("de_state_columns", de_state_columns)


def de_format_shim():
    from reflex_base.utils import format as fmt

    if not hasattr(fmt, "format_data_editor_column"):
        return "no format_data_editor_column"
    import io
    import contextlib

    buf = io.StringIO()
    with warnings.catch_warnings(record=True) as w, contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        warnings.simplefilter("always")
        res = fmt.format_data_editor_column({"title": "A"})
    return {"result": res, "warnings": [str(x.message) for x in w], "stdout": buf.getvalue()[-600:]}


row("de_format_shim", de_format_shim)


# ---- lucide #7604
def lucide_import_var():
    from reflex_base.utils.imports import ImportVar
    from reflex_components_lucide.icon import LUCIDE_LIBRARY

    static = rx.icon("wifi_off")
    dyn = rx.icon(S.name)
    required = ImportVar("icons", alias="lucideIcons")
    size = rx.Var("Object.keys(lucideIcons).length", _var_type=int, _var_data=rx.vars.VarData(imports={LUCIDE_LIBRARY: [required]}))
    with_prop = rx.icon("apple", size=size)
    dyn_with_prop = rx.icon(S.name, size=size)
    cm = rx.icon("sun", color=rx.color_mode_cond("red", "blue"))

    def imps(c):
        return {k: sorted(str(v) for v in vs) for k, vs in c._get_imports().items()}

    return {
        "static_import_var": str(static.import_var),
        "dyn_import_var": str(dyn.import_var),
        "static_imports": imps(static),
        "with_prop_imports": imps(with_prop),
        "with_prop_keeps_lucideIcons": any("lucideIcons" in str(v) for v in with_prop._get_imports().get(LUCIDE_LIBRARY, [])),
        "dyn_with_prop_keeps_lucideIcons": any("lucideIcons" in str(v) for v in dyn_with_prop._get_imports().get(LUCIDE_LIBRARY, [])),
        "cm_all_imports_keys": sorted(cm._get_all_imports().keys()),
        "idempotent": imps(with_prop) == imps(with_prop),
    }


row("lucide_import_var", lucide_import_var)


# ---- code #7437
def shiki_transformers():
    c = rx._x.code_block("print('x')  # [!code highlight]", language="python", use_transformers=True)
    ps = rendered(c)["props"]
    tr = [p for p in ps if p.startswith("transformers:")]
    imports = sorted(c._get_all_imports().keys())
    return {
        "transformers_prop": tr[0][:400] if tr else None,
        "transformers_empty": bool(tr) and tr[0].replace(" ", "").startswith("transformers:[]"),
        "imports": imports,
        "has_shikijs_transformers": any("@shikijs/transformers" in i for i in imports),
        "rsh_library": rx.code_block("x", language="python").library,
        "custom_code_has_highlighted_style": any(".highlighted" in cc for cc in c._get_all_custom_code()),
        "styles": str(c._get_all_custom_code())[:400],
    }


row("shiki_transformers", shiki_transformers)


# ---- VarData(position=) deprecation (#7586)
def vardata_position():
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf), warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        vd = rx.vars.VarData(position=rx.constants.Hooks.HookPosition.PRE_TRIGGER)
    return {"position_attr": repr(getattr(vd, "position", "<no attr>")), "warnings": [str(x.message) for x in w], "console": buf.getvalue()[-500:]}


row("vardata_position", vardata_position)


# ---- misc: themes progress and dialog libraries
def themes_libs():
    return {
        "themes_progress": rx.progress(value=1).library,
        "themes_dialog_content": rx.dialog.content(rx.text("x")).library,
        "slider": rx.slider(default_value=[1]).library,
        "accordion_root": rx.accordion.root(rx.accordion.item(header="h", content="c")).library,
        "drawer_root": rx.drawer.root(rx.drawer.trigger(rx.button("x"))).library,
    }


row("themes_libs", themes_libs)

json.dump({"venv": os.environ.get("EXPECT_VENV", "new"), "reflex": rx.__file__, "rows": rows}, sys.stdout, indent=1, default=str)
print()
