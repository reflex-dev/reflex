"""Integration tests for var operations."""

from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

# pyright: reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false


def VarOperations():
    """App with var operations."""
    from typing import Dict, List

    import reflex as rx
    from reflex.vars.base import LiteralVar
    from reflex.vars.sequence import ArrayVar

    class Object(rx.Base):
        str: str = "hello"

    class VarOperationState(rx.State):
        int_var1: int = 10
        int_var2: int = 5
        int_var3: int = 7
        float_var1: float = 10.5
        float_var2: float = 5.5
        list1: List = [1, 2]
        list2: List = [3, 4]
        list3: List = ["first", "second", "third"]
        list4: List = [Object(name="obj_1"), Object(name="obj_2")]
        str_var1: str = "first"
        str_var2: str = "second"
        str_var3: str = "ThIrD"
        str_var4: str = "a long string"
        dict1: Dict[int, int] = {1: 2}
        dict2: Dict[int, int] = {3: 4}
        html_str: str = "<div>hello</div>"

    app = rx.App(state=rx.State)

    @rx.memo
    def memo_comp(list1: List[int], int_var1: int, id: str):
        return rx.text(list1, int_var1, id=id)

    @rx.memo
    def memo_comp_nested(int_var2: int, id: str):
        return memo_comp(list1=[3, 4], int_var1=int_var2, id=id)

    @app.add_page
    def index():
        return rx.vstack(
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
                VarOperationState.str_var1 | VarOperationState.str_var1, id="str_or_str"
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
                VarOperationState.str_var1 | VarOperationState.int_var2, id="str_or_int"
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
                VarOperationState.str_var1 | VarOperationState.list1, id="str_or_list"
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
                VarOperationState.str_var1 | VarOperationState.dict1, id="str_or_dict"
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
                VarOperationState.list1.contains(1).to_string(), id="list_contains"
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
                VarOperationState.dict1.contains(1).to_string(), id="dict_contains"
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
                    LiteralVar.create(list(range(0, 3))).to(ArrayVar, List[int]),
                    lambda x: rx.foreach(
                        ArrayVar.range(x),
                        lambda y: rx.text(VarOperationState.list1[y], as_="p"),
                    ),
                ),
                id="foreach_list_nested",
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
        app_source=VarOperations,  # type: ignore
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
        token_input = driver.find_element(By.ID, "token")
        assert token_input
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
        # rx.memo component with state
        ("memo_comp", "[1,2]10"),
        ("memo_comp_nested", "[3,4]5"),
        # foreach in a match
        ("foreach_in_match", "first\nsecond\nthird"),
    ]

    for tag, expected in tests:
        print(tag)
        assert driver.find_element(By.ID, tag).text == expected

    # Highlight component with var query (does not plumb ID)
    assert driver.find_element(By.TAG_NAME, "mark").text == "second"
