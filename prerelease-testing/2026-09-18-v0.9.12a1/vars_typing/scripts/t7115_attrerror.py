"""#7115: AttributeError inside a cached var computation must surface chained as ReflexRuntimeError."""
import dataclasses, json, traceback
import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__

@dataclasses.dataclass
class Point:
    x: int = 1
    y: int = 2

@rx.serializer
def serialize_point(p: Point) -> str:
    return f"{p.x},{p.nmae}"     # deliberate typo: .nmae

out = {}

def run(name, fn):
    try:
        fn()
        out[name] = {"raised": None}
    except Exception as e:
        tb = traceback.format_exc()
        chain, cur = [], e
        while cur is not None:
            chain.append(f"{type(cur).__name__}: {cur}")
            cur = cur.__cause__ or cur.__context__
            if len(chain) > 6: break
        out[name] = {
            "type": type(e).__name__,
            "msg": str(e)[:300],
            "cause_type": type(e.__cause__).__name__ if e.__cause__ else None,
            "cause_msg": str(e.__cause__)[:200] if e.__cause__ else None,
            "chain": chain,
            "mentions_nmae": "nmae" in tb,
            "user_frame_in_tb": "serialize_point" in tb,
            "tb_tail": tb.strip().splitlines()[-6:],
        }

run("literal_var_create_list", lambda: str(rx.Var.create([Point()])))
run("var_create_dict", lambda: str(rx.Var.create({"k": [Point()]})))
run("foreach", lambda: str(rx.foreach([Point()], lambda p: rx.text(p.x.to_string()))))
run("custom_attrs_mapping", lambda: rx.box(custom_attrs={"data-p": {"a": Point()}}).render())

# typo inside a computed var body
class S(rx.State):
    n: int = 1
    @rx.var
    def bad(self) -> str:
        return self.nonexistent_attr  # noqa
run("computed_var_body_typo", lambda: __import__("asyncio").get_event_loop())

# hasattr behaviour change flagged in the PR
@dataclasses.dataclass
class Q:
    v: int = 1
@rx.serializer
def serialize_q(q: Q) -> str:
    return q.missing_thing
try:
    v = rx.Var.create([Q()])
    out["hasattr_js_expr"] = {"raised": None, "value": hasattr(v, "_js_expr")}
except Exception as e:
    out["hasattr_js_expr"] = {"type": type(e).__name__, "msg": str(e)[:200]}
try:
    v = rx.Var.create([Q()])
    out["getattr_default"] = {"raised": None, "value": str(getattr(v, "_js_expr", "DEFAULT"))[:80]}
except Exception as e:
    out["getattr_default"] = {"type": type(e).__name__, "msg": str(e)[:200]}

print(json.dumps(out, indent=2, default=str))
