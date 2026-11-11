"""Detail probe: shiki render tree, moment bad-prop errors, radix versions via importlib."""
import importlib, json, os, sys
import reflex as rx
assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
out = {}
mods = {}
for m in ["accordion", "dialog", "drawer", "form", "progress", "slider"]:
    mods[m] = importlib.import_module(f"reflex_components_radix.primitives.{m}")
out["radix_versions"] = {
    "accordion": mods["accordion"].AccordionComponent.library,
    "dialog": mods["dialog"].DialogElement.library,
    "drawer_deps": mods["drawer"].DrawerComponent.lib_dependencies,
    "form": mods["form"].FormComponent.library,
    "progress": mods["progress"].ProgressComponent.library,
    "slider": mods["slider"].SliderComponent.library,
}
c = rx._x.code_block("print('x')  # [!code highlight]", language="python", use_transformers=True)
def walk(comp, depth=0, acc=None):
    acc = acc if acc is not None else []
    r = comp.render() if hasattr(comp, "render") else {}
    acc.append({"depth": depth, "type": type(comp).__name__, "name": r.get("name"), "props": [p[:300] for p in r.get("props", [])]})
    for ch in getattr(comp, "children", []):
        walk(ch, depth + 1, acc)
    return acc
out["shiki_tree"] = walk(c)
out["shiki_custom_code"] = [s[:600] for s in c._get_all_custom_code()]
out["shiki_imports"] = {k: [str(v) for v in vs] for k, vs in c._get_all_imports().items()}
c2 = rx._x.code_block("print('x')", language="python")
out["shiki_plain_tree"] = walk(c2)
# moment bad props
for bad, val in (("filter", rx.Var("(c)=>c")), ("settings", {"a": 1}), ("form_at", "x")):
    try:
        m = rx.moment("2024-03-14", **{bad: val})
        out[f"moment_bad_{bad}"] = m.render().get("props")
    except Exception as e:
        out[f"moment_bad_{bad}"] = f"{type(e).__name__}: {e}"
try:
    out["moment_provider_bad_filter"] = rx.moment_provider(rx.moment("x"), filter=rx.Var("(c)=>c")).render().get("props") if hasattr(rx, "moment_provider") else "n/a"
except Exception as e:
    out["moment_provider_bad_filter"] = f"{type(e).__name__}: {e}"
d = json.load(open(os.path.join(os.path.dirname(__file__), "..", "results", f"probe_compile_{os.environ.get('EXPECT_VENV','new')}.json")))
mp = next(r for r in d["rows"] if r["name"] == "moment_props")["detail"]
out["moment_props_summary"] = {k: (v["props"] if isinstance(v, dict) else v) for k, v in mp.items()}
out["moment_props_css"] = {k: v["css"] for k, v in mp.items() if isinstance(v, dict) and v["css"]}
out["moment_locale_var_imports"] = mp["locale_var"]["imports"] if isinstance(mp["locale_var"], dict) else mp["locale_var"]
out["moment_locale_var_custom_code"] = mp["locale_var"]["custom_code"] if isinstance(mp["locale_var"], dict) else None
out["moment_locale_fr_custom_code"] = mp["locale_fr"]["custom_code"] if isinstance(mp["locale_fr"], dict) else None
json.dump(out, sys.stdout, indent=1, default=str); print()
