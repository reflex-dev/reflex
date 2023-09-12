"""Integration tests for var operations."""
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

# pyright: reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false


def VarOperations():
    """App with var operations."""
    import reflex as rx

    class VarOperationState(rx.State):
        int_var1: int = 10
        int_var2: int = 5
        int_var3: int = 7
        float_var1: float = 10.5
        float_var2: float = 5.5
        list1: list = [1, 2]
        list2: list = [3, 4]
        str_var1: str = "first"
        str_var2: str = "second"
        dict1: dict = {1: 2}
        dict2: dict = {3: 4}

    app = rx.App(state=VarOperationState)

    @app.add_page
    def index():
        return rx.vstack(
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
        )

    app.compile()


@pytest.fixture(scope="session")
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
    """GEt an instance of the browser open to the var operations app.

    Args:
        var_operations: harness for VarOperations app

    Yields:
        WebDriver instance.
    """
    driver = var_operations.frontend()
    try:
        assert var_operations.poll_for_clients()
        yield driver
    finally:
        driver.quit()


def test_var_operations(driver, var_operations: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        driver: selenium WebDriver open to the app
        var_operations: AppHarness for the var operations app
    """
    assert var_operations.app_instance is not None, "app is not running"
    # INT INT
    assert driver.find_element(By.ID, "int_add_int").text == "15"
    assert driver.find_element(By.ID, "int_mult_int").text == "50"
    assert driver.find_element(By.ID, "int_sub_int").text == "5"
    assert driver.find_element(By.ID, "int_exp_int").text == "100000"
    assert driver.find_element(By.ID, "int_div_int").text == "2"
    assert driver.find_element(By.ID, "int_floor_int").text == "1"
    assert driver.find_element(By.ID, "int_mod_int").text == "0"
    assert driver.find_element(By.ID, "int_gt_int").text == "true"
    assert driver.find_element(By.ID, "int_lt_int").text == "false"
    assert driver.find_element(By.ID, "int_gte_int").text == "true"
    assert driver.find_element(By.ID, "int_lte_int").text == "false"
    assert driver.find_element(By.ID, "int_and_int").text == "5"
    assert driver.find_element(By.ID, "int_or_int").text == "10"
    assert driver.find_element(By.ID, "int_eq_int").text == "false"
    assert driver.find_element(By.ID, "int_neq_int").text == "true"

    # INT FLOAT OR FLOAT INT
    assert driver.find_element(By.ID, "float_add_int").text == "15.5"
    assert driver.find_element(By.ID, "float_mult_int").text == "52.5"
    assert driver.find_element(By.ID, "float_sub_int").text == "5.5"
    assert driver.find_element(By.ID, "float_exp_int").text == "127628.15625"
    assert driver.find_element(By.ID, "float_div_int").text == "2.1"
    assert driver.find_element(By.ID, "float_floor_int").text == "1"
    assert driver.find_element(By.ID, "float_mod_int").text == "0.5"
    assert driver.find_element(By.ID, "float_gt_int").text == "true"
    assert driver.find_element(By.ID, "float_lt_int").text == "false"
    assert driver.find_element(By.ID, "float_gte_int").text == "true"
    assert driver.find_element(By.ID, "float_lte_int").text == "false"
    assert driver.find_element(By.ID, "float_eq_int").text == "false"
    assert driver.find_element(By.ID, "float_neq_int").text == "true"
    assert driver.find_element(By.ID, "float_and_int").text == "5"
    assert driver.find_element(By.ID, "float_or_int").text == "10.5"

    # INT, DICT X
    assert driver.find_element(By.ID, "int_or_dict").text == "10"
    assert driver.find_element(By.ID, "int_and_dict").text == '{"1":2}'
    assert driver.find_element(By.ID, "int_eq_dict").text == "false"
    assert driver.find_element(By.ID, "int_neq_dict").text == "true"

    # FLOAT FLOAT
    assert driver.find_element(By.ID, "float_add_float").text == "16"
    assert driver.find_element(By.ID, "float_mult_float").text == "57.75"
    assert driver.find_element(By.ID, "float_sub_float").text == "5"
    assert driver.find_element(By.ID, "float_exp_float").text == "413562.49323606625"
    assert driver.find_element(By.ID, "float_div_float").text == "1.9090909090909092"
    assert driver.find_element(By.ID, "float_floor_float").text == "1"
    assert driver.find_element(By.ID, "float_mod_float").text == "5"
    assert driver.find_element(By.ID, "float_gt_float").text == "true"
    assert driver.find_element(By.ID, "float_lt_float").text == "false"
    assert driver.find_element(By.ID, "float_gte_float").text == "true"
    assert driver.find_element(By.ID, "float_lte_float").text == "false"
    assert driver.find_element(By.ID, "float_eq_float").text == "false"
    assert driver.find_element(By.ID, "float_neq_float").text == "true"
    assert driver.find_element(By.ID, "float_and_float").text == "5.5"
    assert driver.find_element(By.ID, "float_or_float").text == "10.5"

    # FLOAT STR X
    assert driver.find_element(By.ID, "float_or_str").text == "10.5"
    assert driver.find_element(By.ID, "float_and_str").text == "first"
    assert driver.find_element(By.ID, "float_eq_str").text == "false"
    assert driver.find_element(By.ID, "float_neq_str").text == "true"

    # FLOAT,LIST
    assert driver.find_element(By.ID, "float_or_list").text == "10.5"
    assert driver.find_element(By.ID, "float_and_list").text == "[1,2]"
    assert driver.find_element(By.ID, "float_eq_list").text == "false"
    assert driver.find_element(By.ID, "float_neq_list").text == "true"

    # FLOAT, DICT
    assert driver.find_element(By.ID, "float_or_dict").text == "10.5"
    assert driver.find_element(By.ID, "float_and_dict").text == '{"1":2}'
    assert driver.find_element(By.ID, "float_eq_dict").text == "false"
    assert driver.find_element(By.ID, "float_neq_dict").text == "true"

    # STR STR
    assert driver.find_element(By.ID, "str_add_str").text == "firstsecond"
    assert driver.find_element(By.ID, "str_gt_str").text == "false"
    assert driver.find_element(By.ID, "str_lt_str").text == "true"
    assert driver.find_element(By.ID, "str_gte_str").text == "false"
    assert driver.find_element(By.ID, "str_lte_str").text == "true"
    assert driver.find_element(By.ID, "str_eq_str").text == "false"
    assert driver.find_element(By.ID, "str_neq_str").text == "true"
    assert driver.find_element(By.ID, "str_and_str").text == "second"
    assert driver.find_element(By.ID, "str_or_str").text == "first"
    assert driver.find_element(By.ID, "str_contains").text == "true"

    # STR INT
    assert (
        driver.find_element(By.ID, "str_mult_int").text == "firstfirstfirstfirstfirst"
    )
    assert driver.find_element(By.ID, "str_and_int").text == "5"
    assert driver.find_element(By.ID, "str_or_int").text == "first"
    assert driver.find_element(By.ID, "str_eq_int").text == "false"
    assert driver.find_element(By.ID, "str_neq_int").text == "true"

    # STR, LIST
    assert driver.find_element(By.ID, "str_and_list").text == "[1,2]"
    assert driver.find_element(By.ID, "str_or_list").text == "first"
    assert driver.find_element(By.ID, "str_eq_list").text == "false"
    assert driver.find_element(By.ID, "str_neq_list").text == "true"

    # STR, DICT X

    assert driver.find_element(By.ID, "str_or_dict").text == "first"
    assert driver.find_element(By.ID, "str_and_dict").text == '{"1":2}'
    assert driver.find_element(By.ID, "str_eq_dict").text == "false"
    assert driver.find_element(By.ID, "str_neq_dict").text == "true"

    # LIST,LIST
    assert driver.find_element(By.ID, "list_add_list").text == "[1,2,3,4]"
    assert driver.find_element(By.ID, "list_gt_list").text == "false"
    assert driver.find_element(By.ID, "list_lt_list").text == "true"
    assert driver.find_element(By.ID, "list_gte_list").text == "false"
    assert driver.find_element(By.ID, "list_lte_list").text == "true"
    assert driver.find_element(By.ID, "list_eq_list").text == "false"
    assert driver.find_element(By.ID, "list_neq_list").text == "true"
    assert driver.find_element(By.ID, "list_and_list").text == "[3,4]"
    assert driver.find_element(By.ID, "list_or_list").text == "[1,2]"
    assert driver.find_element(By.ID, "list_contains").text == "true"
    assert driver.find_element(By.ID, "list_reverse").text == "[2,1]"

    # LIST INT
    assert driver.find_element(By.ID, "list_mult_int").text == "[1,2,1,2,1,2,1,2,1,2]"
    assert driver.find_element(By.ID, "list_or_int").text == "[1,2]"
    assert driver.find_element(By.ID, "list_and_int").text == "10"
    assert driver.find_element(By.ID, "list_eq_int").text == "false"
    assert driver.find_element(By.ID, "list_neq_int").text == "true"

    # LIST DICT
    assert driver.find_element(By.ID, "list_and_dict").text == '{"1":2}'
    assert driver.find_element(By.ID, "list_or_dict").text == "[1,2]"
    assert driver.find_element(By.ID, "list_eq_dict").text == "false"
    assert driver.find_element(By.ID, "list_neq_dict").text == "true"

    # DICT, DICT
    assert driver.find_element(By.ID, "dict_or_dict").text == '{"1":2}'
    assert driver.find_element(By.ID, "dict_and_dict").text == '{"3":4}'
    assert driver.find_element(By.ID, "dict_eq_dict").text == "false"
    assert driver.find_element(By.ID, "dict_neq_dict").text == "true"
    assert driver.find_element(By.ID, "dict_contains").text == "true"
