"""#7189: Annotated[...] hints resolve to the type they annotate."""
import json
from typing import Annotated, Literal
import reflex as rx
from pydantic import BaseModel, Field
assert "/envs/" in rx.__file__, rx.__file__

class Cat(BaseModel):
    kind: Literal["cat"] = "cat"
    name: str
    lives: int = 9

class Dog(BaseModel):
    kind: Literal["dog"] = "dog"
    name: str
    good: bool = True

Pet = Annotated[Cat | Dog, Field(discriminator="kind")]

out = {"reflex": rx.constants.Reflex.VERSION}

def go(name, fn):
    try:
        out[name] = {"ok": True, "js": str(fn())[:160]}
    except Exception as e:
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:220]}"}

class S(rx.State):
    pet: Pet = Cat(name="Momo")
    pets: list[Pet] = [Cat(name="Momo"), Dog(name="Rex")]
    by_name: dict[str, Pet] = {"momo": Cat(name="Momo")}
    limit: Annotated[int, Field(gt=0)] = 5
    tags: Annotated[list[str], Field(min_length=0)] = ["a"]
    nested: Annotated[Annotated[int, "x"], "y"] = 3

go("var_type_pet", lambda: S.pet._var_type)
go("pet_name", lambda: S.pet.name)
go("pet_kind", lambda: S.pet.kind)
go("pet_lives", lambda: S.pet.lives)
go("dict_value_access", lambda: S.by_name["momo"].name)
go("list_index", lambda: S.pets[0].name)
go("match_on_kind", lambda: rx.match(S.pet.kind, ("cat", "meow"), ("dog", "woof"), "?"))
go("cond_on_kind", lambda: rx.cond(S.pet.kind == "cat", "c", "d"))
go("foreach", lambda: rx.foreach(S.pets, lambda p: rx.text(p.name)))
go("annotated_int_math", lambda: S.limit + 1)
go("annotated_int_type", lambda: S.limit._var_type)
go("annotated_list_len", lambda: S.tags.length())
go("annotated_list_item_upper", lambda: S.tags[0].upper())
go("nested_annotated", lambda: S.nested * 2)

# handler arg typed Annotated
class H(rx.State):
    v: int = 0
    @rx.event
    def take(self, n: Annotated[int, Field(gt=0)]):
        self.v = n
go("handler_annotated_arg", lambda: H.take(3))
go("handler_annotated_arg_spec", lambda: str(H.take))

# typehint_issubclass / resolve_type_alias directly
from reflex_base.utils import types as rtypes
def go2(name, fn):
    try:
        out[name] = {"ok": True, "val": fn()}
    except Exception as e:
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:200]}"}
go2("issubclass_annotated_int_int", lambda: rtypes.typehint_issubclass(Annotated[int, "m"], int))
go2("issubclass_int_annotated_int", lambda: rtypes.typehint_issubclass(int, Annotated[int, "m"]))
go2("resolve_alias_annotated", lambda: str(rtypes.resolve_type_alias(Pet)))
go2("get_attribute_access_type", lambda: str(rtypes.get_attribute_access_type(Pet, "name")))
print(json.dumps(out, indent=2, default=str))
