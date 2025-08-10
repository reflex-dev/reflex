"""Integration tests for var operations."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def VarOperations():
    """App with var operations."""
    from typing import TypedDict

    import reflex as rx
    from reflex.vars.base import LiteralVar
    from reflex.vars.sequence import ArrayVar

    class Object(rx.Base):
        name: str = "hello"
        optional_none: str | None = None
        optional_str: str | None = "hello"

    class Person(TypedDict):
        name: str
        age: int

    class VarOperationState(rx.State):
        int_var1: rx.Field[int] = rx.field(10)
        int_var2: rx.Field[int] = rx.field(5)
        int_var3: rx.Field[int] = rx.field(7)
        float_var1: rx.Field[float] = rx.field(10.5)
        float_var2: rx.Field[float] = rx.field(5.5)
        long_float: rx.Field[float] = rx.field(13212312312.1231231)
        list1: rx.Field[list] = rx.field([1, 2])
        list2: rx.Field[list] = rx.field([3, 4])
        list3: rx.Field[list] = rx.field(["first", "second", "third"])
        list4: rx.Field[list] = rx.field([Object(name="obj_1"), Object(name="obj_2")])
        optional_list: rx.Field[list | None] = rx.field(None)
        optional_dict: rx.Field[dict[str, str] | None] = rx.field(None)
        optional_list_value: rx.Field[list[str] | None] = rx.field(["red", "yellow"])
        optional_dict_value: rx.Field[dict[str, str] | None] = rx.field({"name": "red"})
        str_var1: rx.Field[str] = rx.field("first")
        str_var2: rx.Field[str] = rx.field("second")
        str_var3: rx.Field[str] = rx.field("ThIrD")
        str_var4: rx.Field[str] = rx.field("a long string")
        dict1: rx.Field[dict[int, int]] = rx.field({1: 2})
        dict2: rx.Field[dict[int, int]] = rx.field({3: 4})
        html_str: rx.Field[str] = rx.field("<div>hello</div>")
        people: rx.Field[list[Person]] = rx.field(
            [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        )
        obj: rx.Field[Object] = rx.field(Object())

    app = rx.App()

    @rx.memo
    def memo_comp(list1: list[int], int_var1: int, id: str):
        return rx.text(list1, int_var1, id=id)

    @rx.memo
    def memo_comp_nested(int_var2: int, id: str):
        return memo_comp(list1=[3, 4], int_var1=int_var2, id=id)

    @app.add_page
    def index():
        return rx.vstack(
            None,  # Testing that None doesn't break everything
            rx.el.input(
                id="token",
                value=VarOperationState.router.session.client_token,
                is_read_only=True,
            ),
            # INT INT
            rx.text(
                VarOperationState.int_var1 + VarOperationState.int_var2,
                id="int_add_int",
            ),
            rx.text(
                VarOperationState.int_var1 * VarOperationState.int_var2,
                id="int_mult_int",
            ),
            rx.text(
                VarOperationState.int_var1 - VarOperationState.int_var2,
                id="int_sub_int",
            ),
            rx.text(
                VarOperationState.int_var1**VarOperationState.int_var2,
                id="int_exp_int",
            ),
            rx.text(
                VarOperationState.int_var1 / VarOperationState.int_var2,
                id="int_div_int",
            ),
            rx.text(
                VarOperationState.int_var1 // VarOperationState.int_var3,
                id="int_floor_int",
            ),
            rx.text(
                VarOperationState.int_var1 % VarOperationState.int_var2,
                id="int_mod_int",
            ),
            rx.text(
                VarOperationState.int_var1 | VarOperationState.int_var2,
                id="int_or_int",
            ),
            rx.text(
                (VarOperationState.int_var1 > VarOperationState.int_var2).to_string(),
                id="int_gt_int",
            ),
            rx.text(
                (VarOperationState.int_var1 < VarOperationState.int_var2).to_string(),
                id="int_lt_int",
            ),
            rx.text(
                (VarOperationState.int_var1 >= VarOperationState.int_var2).to_string(),
                id="int_gte_int",
            ),
            rx.text(
                (VarOperationState.int_var1 <= VarOperationState.int_var2).to_string(),
                id="int_lte_int",
            ),
            rx.text(
                VarOperationState.int_var1 & VarOperationState.int_var2,
                id="int_and_int",
            ),
            rx.text(
                (VarOperationState.int_var1 | VarOperationState.int_var2).to_string(),
                id="int_or_int",
            ),
            rx.text(
                (VarOperationState.int_var1 == VarOperationState.int_var2).to_string(),
                id="int_eq_int",
            ),
            rx.text(
                (VarOperationState.int_var1 != VarOperationState.int_var2).to_string(),
                id="int_neq_int",
            ),
            # INT FLOAT OR FLOAT INT
            rx.text(
                VarOperationState.float_var1 + VarOperationState.int_var2,
                id="float_add_int",
            ),
            rx.text(
                VarOperationState.float_var1 * VarOperationState.int_var2,
                id="float_mult_int",
            ),
            rx.text(
                VarOperationState.float_var1 - VarOperationState.int_var2,
                id="float_sub_int",
            ),
            rx.text(
                VarOperationState.float_var1**VarOperationState.int_var2,
                id="float_exp_int",
            ),
            rx.text(
                VarOperationState.float_var1 / VarOperationState.int_var2,
                id="float_div_int",
            ),
            rx.text(
                VarOperationState.float_var1 // VarOperationState.int_var3,
                id="float_floor_int",
            ),
            rx.text(
                VarOperationState.float_var1 % VarOperationState.int_var2,
                id="float_mod_int",
            ),
            rx.text(
                (VarOperationState.float_var1 > VarOperationState.int_var2).to_string(),
                id="float_gt_int",
            ),
            rx.text(
                (VarOperationState.float_var1 < VarOperationState.int_var2).to_string(),
                id="float_lt_int",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 >= VarOperationState.int_var2
                ).to_string(),
                id="float_gte_int",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 <= VarOperationState.int_var2
                ).to_string(),
                id="float_lte_int",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 == VarOperationState.int_var2
                ).to_string(),
                id="float_eq_int",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 != VarOperationState.int_var2
                ).to_string(),
                id="float_neq_int",
            ),
            rx.text(
                (VarOperationState.float_var1 & VarOperationState.int_var2).to_string(),
                id="float_and_int",
            ),
            rx.text(
                (VarOperationState.float_var1 | VarOperationState.int_var2).to_string(),
                id="float_or_int",
            ),
            # INT, DICT
            rx.text(
                (VarOperationState.int_var1 | VarOperationState.dict1).to_string(),
                id="int_or_dict",
            ),
            rx.text(
                (VarOperationState.int_var1 & VarOperationState.dict1).to_string(),
                id="int_and_dict",
            ),
            rx.text(
                (VarOperationState.int_var1 == VarOperationState.dict1).to_string(),
                id="int_eq_dict",
            ),
            rx.text(
                (VarOperationState.int_var1 != VarOperationState.dict1).to_string(),
                id="int_neq_dict",
            ),
            # FLOAT FLOAT
            rx.text(
                VarOperationState.float_var1 + VarOperationState.float_var2,
                id="float_add_float",
            ),
            rx.text(
                VarOperationState.float_var1 * VarOperationState.float_var2,
                id="float_mult_float",
            ),
            rx.text(
                VarOperationState.float_var1 - VarOperationState.float_var2,
                id="float_sub_float",
            ),
            rx.text(
                VarOperationState.float_var1**VarOperationState.float_var2,
                id="float_exp_float",
            ),
            rx.text(
                VarOperationState.float_var1 / VarOperationState.float_var2,
                id="float_div_float",
            ),
            rx.text(
                VarOperationState.float_var1 // VarOperationState.float_var2,
                id="float_floor_float",
            ),
            rx.text(
                VarOperationState.float_var1 % VarOperationState.float_var2,
                id="float_mod_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 > VarOperationState.float_var2
                ).to_string(),
                id="float_gt_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 < VarOperationState.float_var2
                ).to_string(),
                id="float_lt_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 >= VarOperationState.float_var2
                ).to_string(),
                id="float_gte_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 <= VarOperationState.float_var2
                ).to_string(),
                id="float_lte_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 == VarOperationState.float_var2
                ).to_string(),
                id="float_eq_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 != VarOperationState.float_var2
                ).to_string(),
                id="float_neq_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 & VarOperationState.float_var2
                ).to_string(),
                id="float_and_float",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 | VarOperationState.float_var2
                ).to_string(),
                id="float_or_float",
            ),
            # FLOAT STR
            rx.text(
                VarOperationState.float_var1 | VarOperationState.str_var1,
                id="float_or_str",
            ),
            rx.text(
                VarOperationState.float_var1 & VarOperationState.str_var1,
                id="float_and_str",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 == VarOperationState.str_var1
                ).to_string(),
                id="float_eq_str",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 != VarOperationState.str_var1
                ).to_string(),
                id="float_neq_str",
            ),
            # FLOAT LIST
            rx.text(
                (VarOperationState.float_var1 | VarOperationState.list1).to_string(),
                id="float_or_list",
            ),
            rx.text(
                (VarOperationState.float_var1 & VarOperationState.list1).to_string(),
                id="float_and_list",
            ),
            rx.text(
                (VarOperationState.float_var1 == VarOperationState.list1).to_string(),
                id="float_eq_list",
            ),
            rx.text(
                (VarOperationState.float_var1 != VarOperationState.list1).to_string(),
                id="float_neq_list",
            ),
            # FLOAT DICT
            rx.text(
                (VarOperationState.float_var1 | VarOperationState.dict1).to_string(),
                id="float_or_dict",
            ),
            rx.text(
                (VarOperationState.float_var1 & VarOperationState.dict1).to_string(),
                id="float_and_dict",
            ),
            rx.text(
                (VarOperationState.float_var1 == VarOperationState.dict1).to_string(),
                id="float_eq_dict",
            ),
            rx.text(
                (VarOperationState.float_var1 != VarOperationState.dict1).to_string(),
                id="float_neq_dict",
            ),
            # STR STR
            rx.text(
                VarOperationState.str_var1 + VarOperationState.str_var2,
                id="str_add_str",
            ),
            rx.text(
                (VarOperationState.str_var1 > VarOperationState.str_var2).to_string(),
                id="str_gt_str",
            ),
            rx.text(
                (VarOperationState.str_var1 < VarOperationState.str_var2).to_string(),
                id="str_lt_str",
            ),
            rx.text(
                (VarOperationState.str_var1 >= VarOperationState.str_var2).to_string(),
                id="str_gte_str",
            ),
            rx.text(
                (VarOperationState.str_var1 <= VarOperationState.str_var2).to_string(),
                id="str_lte_str",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 == VarOperationState.float_var2
                ).to_string(),
                id="str_eq_str",
            ),
            rx.text(
                (
                    VarOperationState.float_var1 != VarOperationState.float_var2
                ).to_string(),
                id="str_neq_str",
            ),
            rx.text(
                VarOperationState.str_var1.contains("fir").to_string(),
                id="str_contains",
            ),
            rx.text(
                VarOperationState.str_var1 | VarOperationState.str_var1,
                id="str_or_str",
            ),
            rx.text(
                VarOperationState.str_var1 & VarOperationState.str_var2,
                id="str_and_str",
            ),
            # STR, INT
            rx.text(
                VarOperationState.str_var1 * VarOperationState.int_var2,
                id="str_mult_int",
            ),
            rx.text(
                VarOperationState.str_var1 & VarOperationState.int_var2,
                id="str_and_int",
            ),
            rx.text(
                VarOperationState.str_var1 | VarOperationState.int_var2,
                id="str_or_int",
            ),
            rx.text(
                (VarOperationState.str_var1 == VarOperationState.int_var1).to_string(),
                id="str_eq_int",
            ),
            rx.text(
                (VarOperationState.str_var1 != VarOperationState.int_var1).to_string(),
                id="str_neq_int",
            ),
            # STR, LIST
            rx.text(
                VarOperationState.str_var1 | VarOperationState.list1,
                id="str_or_list",
            ),
            rx.text(
                (VarOperationState.str_var1 & VarOperationState.list1).to_string(),
                id="str_and_list",
            ),
            rx.text(
                (VarOperationState.str_var1 == VarOperationState.list1).to_string(),
                id="str_eq_list",
            ),
            rx.text(
                (VarOperationState.str_var1 != VarOperationState.list1).to_string(),
                id="str_neq_list",
            ),
            # STR, DICT
            rx.text(
                VarOperationState.str_var1 | VarOperationState.dict1,
                id="str_or_dict",
            ),
            rx.text(
                (VarOperationState.str_var1 & VarOperationState.dict1).to_string(),
                id="str_and_dict",
            ),
            rx.text(
                (VarOperationState.str_var1 == VarOperationState.dict1).to_string(),
                id="str_eq_dict",
            ),
            rx.text(
                (VarOperationState.str_var1 != VarOperationState.dict1).to_string(),
                id="str_neq_dict",
            ),
            # LIST, LIST
            rx.text(
                (VarOperationState.list1 + VarOperationState.list2).to_string(),
                id="list_add_list",
            ),
            rx.text(
                (VarOperationState.list1 & VarOperationState.list2).to_string(),
                id="list_and_list",
            ),
            rx.text(
                (VarOperationState.list1 | VarOperationState.list2).to_string(),
                id="list_or_list",
            ),
            rx.text(
                (VarOperationState.list1 > VarOperationState.list2).to_string(),
                id="list_gt_list",
            ),
            rx.text(
                (VarOperationState.list1 < VarOperationState.list2).to_string(),
                id="list_lt_list",
            ),
            rx.text(
                (VarOperationState.list1 >= VarOperationState.list2).to_string(),
                id="list_gte_list",
            ),
            rx.text(
                (VarOperationState.list1 <= VarOperationState.list2).to_string(),
                id="list_lte_list",
            ),
            rx.text(
                (VarOperationState.list1 == VarOperationState.list2).to_string(),
                id="list_eq_list",
            ),
            rx.text(
                (VarOperationState.list1 != VarOperationState.list2).to_string(),
                id="list_neq_list",
            ),
            rx.text(
                VarOperationState.list1.contains(1).to_string(),
                id="list_contains",
            ),
            rx.text(VarOperationState.list4.pluck("name").to_string(), id="list_pluck"),
            rx.text(VarOperationState.list1.reverse().to_string(), id="list_reverse"),
            # LIST, INT
            rx.text(
                (VarOperationState.list1 * VarOperationState.int_var2).to_string(),
                id="list_mult_int",
            ),
            rx.text(
                (VarOperationState.list1 | VarOperationState.int_var1).to_string(),
                id="list_or_int",
            ),
            rx.text(
                (VarOperationState.list1 & VarOperationState.int_var1).to_string(),
                id="list_and_int",
            ),
            rx.text(
                (VarOperationState.list1 == VarOperationState.int_var1).to_string(),
                id="list_eq_int",
            ),
            rx.text(
                (VarOperationState.list1 != VarOperationState.int_var1).to_string(),
                id="list_neq_int",
            ),
            # LIST, DICT
            rx.text(
                (VarOperationState.list1 | VarOperationState.dict1).to_string(),
                id="list_or_dict",
            ),
            rx.text(
                (VarOperationState.list1 & VarOperationState.dict1).to_string(),
                id="list_and_dict",
            ),
            rx.text(
                (VarOperationState.list1 == VarOperationState.dict1).to_string(),
                id="list_eq_dict",
            ),
            rx.text(
                (VarOperationState.list1 != VarOperationState.dict1).to_string(),
                id="list_neq_dict",
            ),
            # DICT, DICT
            rx.text(
                (VarOperationState.dict1 | VarOperationState.dict2).to_string(),
                id="dict_or_dict",
            ),
            rx.text(
                (VarOperationState.dict1 & VarOperationState.dict2).to_string(),
                id="dict_and_dict",
            ),
            rx.text(
                (VarOperationState.dict1 == VarOperationState.dict2).to_string(),
                id="dict_eq_dict",
            ),
            rx.text(
                (VarOperationState.dict1 != VarOperationState.dict2).to_string(),
                id="dict_neq_dict",
            ),
            rx.text(
                VarOperationState.dict1.contains(1).to_string(),
                id="dict_contains",
            ),
            rx.text(VarOperationState.str_var3.lower(), id="str_lower"),
            rx.text(VarOperationState.str_var3.upper(), id="str_upper"),
            rx.text(VarOperationState.str_var4.split(" ").to_string(), id="str_split"),
            rx.text(VarOperationState.list3.join(""), id="list_join"),
            rx.text(VarOperationState.list3.join(","), id="list_join_comma"),
            # Index from an op var
            rx.text(
                VarOperationState.list3[VarOperationState.int_var1 % 3],
                id="list_index_mod",
            ),
            rx.html(
                VarOperationState.html_str,
                id="html_str",
            ),
            rx.el.mark("second"),
            rx.text(ArrayVar.range(2, 5).join(","), id="list_join_range1"),
            rx.text(ArrayVar.range(2, 10, 2).join(","), id="list_join_range2"),
            rx.text(ArrayVar.range(5, 0, -1).join(","), id="list_join_range3"),
            rx.text(ArrayVar.range(0, 3).join(","), id="list_join_range4"),
            rx.box(
                rx.foreach(
                    ArrayVar.range(0, 2),
                    lambda x: rx.text(VarOperationState.list1[x], as_="p"),
                ),
                id="foreach_list_arg",
            ),
            rx.box(
                rx.foreach(
                    ArrayVar.range(0, 2),
                    lambda x, ix: rx.text(VarOperationState.list1[ix], as_="p"),
                ),
                id="foreach_list_ix",
            ),
            rx.box(
                rx.foreach(
                    LiteralVar.create(list(range(3))).to(ArrayVar, list[int]),
                    lambda x: rx.foreach(
                        ArrayVar.range(x),
                        lambda y: rx.text(VarOperationState.list1[y], as_="p"),
                    ),
                ),
                id="foreach_list_nested",
            ),
            rx.box(
                rx.foreach(
                    ArrayVar.range(0, 2),
                    lambda x: VarOperationState.list1[x],
                ),
                id="foreach_list_arg2",
            ),
            memo_comp(
                list1=VarOperationState.list1,
                int_var1=VarOperationState.int_var1,
                id="memo_comp",
            ),
            memo_comp_nested(
                int_var2=VarOperationState.int_var2,
                id="memo_comp_nested",
            ),
            # length
            rx.box(
                rx.text(VarOperationState.list3.length()),
                id="list_length",
            ),
            rx.box(
                rx.text(VarOperationState.obj.length()),
                id="obj_length",
            ),
            # foreach in a match
            rx.box(
                rx.match(
                    VarOperationState.list3.length(),
                    (0, rx.text("No choices")),
                    (1, rx.text("One choice")),
                    rx.foreach(VarOperationState.list3, lambda choice: rx.text(choice)),
                ),
                id="foreach_in_match",
            ),
            # Literal range var in a foreach
            rx.box(rx.foreach(range(42, 80, 27), rx.text.span), id="range_in_foreach1"),
            rx.box(rx.foreach(range(42, 80, 3), rx.text.span), id="range_in_foreach2"),
            rx.box(rx.foreach(range(42, 20, -6), rx.text.span), id="range_in_foreach3"),
            rx.box(rx.foreach(range(42, 43, 5), rx.text.span), id="range_in_foreach4"),
            # Literal dict in a foreach
            rx.box(rx.foreach({"a": 1, "b": 2}, rx.text.span), id="dict_in_foreach1"),
            # State Var dict in a foreach
            rx.box(
                rx.foreach(VarOperationState.dict1, rx.text.span),
                id="dict_in_foreach2",
            ),
            rx.box(
                rx.foreach(
                    VarOperationState.dict1.merge(VarOperationState.dict2),
                    rx.text.span,
                ),
                id="dict_in_foreach3",
            ),
            rx.box(
                rx.foreach("abcdef", lambda x: rx.text.span(x + " ")),
                id="str_in_foreach",
            ),
            rx.box(
                rx.foreach(VarOperationState.str_var1, lambda x: rx.text.span(x + " ")),
                id="str_var_in_foreach",
            ),
            rx.box(
                rx.foreach(
                    VarOperationState.people,
                    lambda person: rx.text.span(
                        "Hello " + person["name"], person["age"] + 3
                    ),
                ),
                id="typed_dict_in_foreach",
            ),
            rx.box(
                rx.foreach(VarOperationState.optional_list, rx.text.span),
                id="optional_list",
            ),
            rx.box(
                rx.foreach(VarOperationState.optional_dict, rx.text.span),
                id="optional_dict",
            ),
            rx.box(
                rx.foreach(VarOperationState.optional_list_value, rx.text.span),
                id="optional_list_value",
            ),
            rx.box(
                rx.foreach(VarOperationState.optional_dict_value, rx.text.span),
                id="optional_dict_value",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231)}"),
                id="float_format",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):.0f}"),
                id="float_format_0f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):.1f}"),
                id="float_format_1f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):.2f}"),
                id="float_format_2f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):,}"),
                id="float_format_comma",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):_}"),
                id="float_format_underscore",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):,.0f}"),
                id="float_format_comma_0f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):,.1f}"),
                id="float_format_comma_1f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):,.2f}"),
                id="float_format_comma_2f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):_.0f}"),
                id="float_format_underscore_0f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):_.1f}"),
                id="float_format_underscore_1f",
            ),
            rx.box(
                rx.text.span(f"{rx.Var.create(13212312312.1231231):_.2f}"),
                id="float_format_underscore_2f",
            ),
            # ObjectVar
            rx.box(
                rx.text.span(VarOperationState.obj.name),
                id="obj_name",
            ),
            rx.box(
                rx.text.span(VarOperationState.obj.optional_none),
                id="obj_optional_none",
            ),
            rx.box(
                rx.text.span(VarOperationState.obj.optional_str),
                id="obj_optional_str",
            ),
            rx.box(
                rx.text.span(VarOperationState.obj.get("optional_none")),
                id="obj_optional_none_get_none",
            ),
            rx.box(
                rx.text.span(VarOperationState.obj.get("optional_none", "foo")),
                id="obj_optional_none_get_foo",
            ),
            rx.box(
                rx.text.span(round(VarOperationState.long_float)),
                id="float_round",
            ),
            rx.box(
                rx.text.span(round(VarOperationState.long_float, 2)),
                id="float_round_2",
            ),
        )


@pytest.fixture(scope="module")
def var_operations(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start VarOperations app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("var_operations"),
        app_source=VarOperations,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(var_operations: AppHarness):
    """Get an instance of the browser open to the var operations app.

    Args:
        var_operations: harness for VarOperations app

    Yields:
        WebDriver instance.
    """
    driver = var_operations.frontend()
    try:
        token_input = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        # wait for the backend connection to send the token
        token = var_operations.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


def test_var_operations(driver, var_operations: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        driver: selenium WebDriver open to the app
        var_operations: AppHarness for the var operations app
    """
    tests = [
        # int, int
        ("int_add_int", "15"),
        ("int_mult_int", "50"),
        ("int_sub_int", "5"),
        ("int_exp_int", "100000"),
        ("int_div_int", "2"),
        ("int_floor_int", "1"),
        ("int_mod_int", "0"),
        ("int_gt_int", "true"),
        ("int_lt_int", "false"),
        ("int_gte_int", "true"),
        ("int_lte_int", "false"),
        ("int_and_int", "5"),
        ("int_or_int", "10"),
        ("int_eq_int", "false"),
        ("int_neq_int", "true"),
        # int, float
        ("float_add_int", "15.5"),
        ("float_mult_int", "52.5"),
        ("float_sub_int", "5.5"),
        ("float_exp_int", "127628.15625"),
        ("float_div_int", "2.1"),
        ("float_floor_int", "1"),
        ("float_mod_int", "0.5"),
        ("float_gt_int", "true"),
        ("float_lt_int", "false"),
        ("float_gte_int", "true"),
        ("float_lte_int", "false"),
        ("float_eq_int", "false"),
        ("float_neq_int", "true"),
        ("float_and_int", "5"),
        ("float_or_int", "10.5"),
        # int, dict
        ("int_or_dict", "10"),
        ("int_and_dict", '{"1":2}'),
        ("int_eq_dict", "false"),
        ("int_neq_dict", "true"),
        # float, float
        ("float_add_float", "16"),
        ("float_mult_float", "57.75"),
        ("float_sub_float", "5"),
        ("float_exp_float", "413562.49323606625"),
        ("float_div_float", "1.9090909090909092"),
        ("float_floor_float", "1"),
        ("float_mod_float", "5"),
        ("float_gt_float", "true"),
        ("float_lt_float", "false"),
        ("float_gte_float", "true"),
        ("float_lte_float", "false"),
        ("float_eq_float", "false"),
        ("float_neq_float", "true"),
        ("float_and_float", "5.5"),
        ("float_or_float", "10.5"),
        # float, str
        ("float_or_str", "10.5"),
        ("float_and_str", "first"),
        ("float_eq_str", "false"),
        ("float_neq_str", "true"),
        # float, list
        ("float_or_list", "10.5"),
        ("float_and_list", "[1,2]"),
        ("float_eq_list", "false"),
        ("float_neq_list", "true"),
        # float, dict
        ("float_or_dict", "10.5"),
        ("float_and_dict", '{"1":2}'),
        ("float_eq_dict", "false"),
        ("float_neq_dict", "true"),
        # str, str
        ("str_add_str", "firstsecond"),
        ("str_gt_str", "false"),
        ("str_lt_str", "true"),
        ("str_gte_str", "false"),
        ("str_lte_str", "true"),
        ("str_eq_str", "false"),
        ("str_neq_str", "true"),
        ("str_and_str", "second"),
        ("str_or_str", "first"),
        ("str_contains", "true"),
        ("str_lower", "third"),
        ("str_upper", "THIRD"),
        ("str_split", '["a","long","string"]'),
        # str, int
        ("str_mult_int", "firstfirstfirstfirstfirst"),
        ("str_and_int", "5"),
        ("str_or_int", "first"),
        ("str_eq_int", "false"),
        ("str_neq_int", "true"),
        # str, list
        ("str_and_list", "[1,2]"),
        ("str_or_list", "first"),
        ("str_eq_list", "false"),
        ("str_neq_list", "true"),
        # str, dict
        ("str_or_dict", "first"),
        ("str_and_dict", '{"1":2}'),
        ("str_eq_dict", "false"),
        ("str_neq_dict", "true"),
        # list, list
        ("list_add_list", "[1,2,3,4]"),
        ("list_gt_list", "false"),
        ("list_lt_list", "true"),
        ("list_gte_list", "false"),
        ("list_lte_list", "true"),
        ("list_eq_list", "false"),
        ("list_neq_list", "true"),
        ("list_and_list", "[3,4]"),
        ("list_or_list", "[1,2]"),
        ("list_contains", "true"),
        ("list_pluck", '["obj_1","obj_2"]'),
        ("list_reverse", "[2,1]"),
        ("list_join", "firstsecondthird"),
        ("list_join_comma", "first,second,third"),
        ("list_join_range1", "2,3,4"),
        ("list_join_range2", "2,4,6,8"),
        ("list_join_range3", "5,4,3,2,1"),
        ("list_join_range4", "0,1,2"),
        # list, int
        ("list_mult_int", "[1,2,1,2,1,2,1,2,1,2]"),
        ("list_or_int", "[1,2]"),
        ("list_and_int", "10"),
        ("list_eq_int", "false"),
        ("list_neq_int", "true"),
        # list, dict
        ("list_and_dict", '{"1":2}'),
        ("list_or_dict", "[1,2]"),
        ("list_eq_dict", "false"),
        ("list_neq_dict", "true"),
        # dict, dict
        ("dict_or_dict", '{"1":2}'),
        ("dict_and_dict", '{"3":4}'),
        ("dict_eq_dict", "false"),
        ("dict_neq_dict", "true"),
        ("dict_contains", "true"),
        # index from an op var
        ("list_index_mod", "second"),
        # html component with var
        ("html_str", "hello"),
        # index into list with foreach
        ("foreach_list_arg", "1\n2"),
        ("foreach_list_ix", "1\n2"),
        ("foreach_list_nested", "1\n1\n2"),
        ("foreach_list_arg2", "12"),
        # rx.memo component with state
        ("memo_comp", "1210"),
        ("memo_comp_nested", "345"),
        # length
        ("list_length", "3"),
        ("obj_length", "3"),
        # foreach in a match
        ("foreach_in_match", "first\nsecond\nthird"),
        # literal range in a foreach
        ("range_in_foreach1", "4269"),
        ("range_in_foreach2", "42454851545760636669727578"),
        ("range_in_foreach3", "42363024"),
        ("range_in_foreach4", "42"),
        ("dict_in_foreach1", "a1b2"),
        ("dict_in_foreach2", "12"),
        ("dict_in_foreach3", "1234"),
        ("str_in_foreach", "a b c d e f"),
        ("str_var_in_foreach", "f i r s t"),
        ("typed_dict_in_foreach", "Hello Alice33Hello Bob28"),
        # fstring operations
        ("float_format", "13212312312.123123"),
        ("float_format_0f", "13212312312"),
        ("float_format_1f", "13212312312.1"),
        ("float_format_2f", "13212312312.12"),
        ("float_format_comma", "13,212,312,312.123"),
        ("float_format_underscore", "13_212_312_312.123"),
        ("float_format_comma_0f", "13,212,312,312"),
        ("float_format_comma_1f", "13,212,312,312.1"),
        ("float_format_comma_2f", "13,212,312,312.12"),
        ("float_format_underscore_0f", "13_212_312_312"),
        ("float_format_underscore_1f", "13_212_312_312.1"),
        ("float_format_underscore_2f", "13_212_312_312.12"),
        ("obj_name", "hello"),
        ("obj_optional_none", ""),
        ("obj_optional_str", "hello"),
        ("obj_optional_none_get_none", ""),
        ("obj_optional_none_get_foo", "foo"),
        ("float_round", "13212312312"),
        ("float_round_2", "13212312312.12"),
    ]

    for tag, expected in tests:
        existing = driver.find_element(By.ID, tag).text
        assert existing == expected, (
            f"Failed on {tag}, expected {expected} but got {existing}"
        )

    # Highlight component with var query (does not plumb ID)
    assert driver.find_element(By.TAG_NAME, "mark").text == "second"
