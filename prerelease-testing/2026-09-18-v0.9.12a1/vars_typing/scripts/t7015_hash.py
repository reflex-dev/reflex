"""#7015: Var hashing derived from Var.equals identity."""
import sys, json
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
print("REFLEX:", rx.__file__)
from reflex.vars import Var, VarData
import reflex_base
print("reflex_base:", reflex_base.__file__)

results = {}

# --- 1. two vars, same js expr, different VarData, in ONE f-string
v_plain = Var("myval")
v_meta = Var(
    "myval",
    _var_data=VarData(
        hooks={"const myval = useFancyHook();": None},
        imports={"$/fancy": [rx.vars.base.ImportVar(tag="useFancyHook")]},
    ),
)
combined = rx.Var.create(f"{v_plain} + {v_meta}")
vd = combined._get_all_var_data()
results["fstring_same_value_diff_vardata"] = {
    "js": str(combined),
    "hooks": list(vd.hooks) if vd else [],
    "imports": str(vd.imports) if vd else "",
    "hash_differs": hash(v_plain) != hash(v_meta),
    "equals": v_plain.equals(v_meta),
}

# reverse order too
combined2 = rx.Var.create(f"{v_meta} + {v_plain}")
vd2 = combined2._get_all_var_data()
results["fstring_reverse_order_hooks"] = list(vd2.hooks) if vd2 else []

# --- 2. color_mode + same-valued plain var
cm = rx.color_mode
plain_cm = Var(str(cm))
both = rx.Var.create(f"{cm}|{plain_cm}")
vdb = both._get_all_var_data()
results["color_mode_plus_plain"] = {
    "js": str(both),
    "hooks": list(vdb.hooks) if vdb else [],
    "n_imports": len(vdb.imports) if vdb else 0, "imports": str(vdb.imports) if vdb else "",
}

# --- 3. hashability
class S(rx.State):
    count: int = 0
    name: str = "x"
    flag: bool = False

    @rx.var
    def doubled(self) -> int:
        return self.count * 2

    @rx.var
    def is_big(self) -> bool:
        return self.count > 5

try:
    h = hash(S.count + 1)
    results["hash_numbervar_op"] = {"ok": True, "hash": str(h)}
except Exception as e:
    results["hash_numbervar_op"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

try:
    s = {S.count, S.name, S.flag, S.doubled, S.is_big, S.count}
    results["set_of_vars"] = {"ok": True, "len": len(s)}
except Exception as e:
    results["set_of_vars"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

try:
    d = {S.count: "a", S.flag: "b", S.count + 1: "c"}
    results["dict_keys_number_bool"] = {"ok": True, "len": len(d)}
except Exception as e:
    results["dict_keys_number_bool"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# --- 4. equals on vars with deps (computed var)
try:
    results["computed_equals_self"] = {"ok": True, "val": S.doubled.equals(S.doubled)}
except Exception as e:
    results["computed_equals_self"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
try:
    results["computed_equals_other"] = {"ok": True, "val": S.doubled.equals(S.is_big)}
except Exception as e:
    results["computed_equals_other"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
try:
    results["computed_hash_consistency"] = {
        "ok": True,
        "same": hash(S.doubled) == hash(S.doubled),
        "diff_from_other": hash(S.doubled) != hash(S.is_big),
    }
except Exception as e:
    results["computed_hash_consistency"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# --- 5. rx.match with number/bool var keys (cond values)
try:
    m = rx.match(S.count, (1, "one"), (2, "two"), "other")
    results["match_ok"] = {"ok": True, "js_len": len(str(m))}
except Exception as e:
    results["match_ok"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# --- 6. hash consistency with .to()
try:
    a = S.count
    b = S.count.to(rx.vars.NumberVar)
    results["to_hash_consistency"] = {"ok": True, "equal_hash": hash(a) == hash(b), "equals": a.equals(b)}
except Exception as e:
    results["to_hash_consistency"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# --- 7. hash key contains no Var objects
try:
    key = S.doubled._hash_key()
    def has_var(o, depth=0):
        if depth > 8: return False
        if isinstance(o, Var): return True
        if isinstance(o, (tuple, list, set, frozenset)):
            return any(has_var(x, depth+1) for x in o)
        if isinstance(o, dict):
            return any(has_var(k, depth+1) or has_var(v, depth+1) for k, v in o.items())
        return False
    results["hash_key_no_vars"] = {"ok": True, "clean": not has_var(key)}
except Exception as e:
    results["hash_key_no_vars"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

print(json.dumps(results, indent=2, default=str))
