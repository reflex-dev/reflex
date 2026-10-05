"""#7015 targeted: LITERAL vars with equal value but different VarData in one f-string.

On 0.9.11.post1 Literal*Var.__hash__ ignores _var_data, so both interpolations
decode to whichever var landed in _global_vars last -> hooks/imports silently dropped.
"""
import json
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
from reflex.vars import Var, VarData
from reflex.vars.base import ImportVar

def mkdata(n):
    return VarData(hooks={f"const h{n} = useHook{n}();": None},
                   imports={f"$/lib{n}": [ImportVar(tag=f"useHook{n}")]})

out = {}

def probe(name, plain, meta):
    r = {}
    r["hash_equal"] = hash(plain) == hash(meta)
    for label, expr in (("meta_first", f"{meta}|{plain}"), ("plain_first", f"{plain}|{meta}")):
        v = rx.Var.create(expr)
        vd = v._get_all_var_data()
        r[label] = {
            "js": str(v),
            "hooks": sorted(vd.hooks) if vd else [],
            "imports": sorted(k for k, _ in (vd.imports or ())) if vd else [],
        }
    out[name] = r

# number literal
probe("number_literal_5", rx.Var.create(5), rx.Var.create(5, _var_data=mkdata("N")))
# bool literal
probe("bool_literal_true", rx.Var.create(True), rx.Var.create(True, _var_data=mkdata("B")))
# string literal
probe("string_literal", rx.Var.create("abc"), rx.Var.create("abc", _var_data=mkdata("S")))
# array literal
probe("array_literal", rx.Var.create([1, 2]), rx.Var.create([1, 2], _var_data=mkdata("A")))
# object literal
probe("object_literal", rx.Var.create({"k": 1}), rx.Var.create({"k": 1}, _var_data=mkdata("O")))

# Realistic: the same literal used plainly and inside a component that needs a hook
class St(rx.State):
    n: int = 5

# color-mode-ish: rx.cond over a literal carrying a hook, vs plain literal
lit_plain = rx.Var.create(1)
lit_hooked = rx.Var.create(1, _var_data=VarData(
    hooks={"const myRef = useRef(null);": None},
    imports={"react": [ImportVar(tag="useRef")]}))
comp = rx.box(f"{lit_hooked} and {lit_plain}")
out["component_box_fstring"] = {
    "hooks": sorted(comp._get_all_hooks()),
    "imports": sorted(comp._get_all_imports()),
}
comp_rev = rx.box(f"{lit_plain} and {lit_hooked}")
out["component_box_fstring_rev"] = {
    "hooks": sorted(comp_rev._get_all_hooks()),
    "imports": sorted(comp_rev._get_all_imports()),
}
print(json.dumps(out, indent=2, default=str))
