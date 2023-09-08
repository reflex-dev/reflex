"""Integration tests for var operations."""
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


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
                VarOperationState.int_var1 ** VarOperationState.int_var2,
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
            rx.text(VarOperationState.int_var1 % VarOperationState.int_var2, id="int_mod_int"),
            rx.text(
                VarOperationState.int_var1 | VarOperationState.int_var2,
                id="int_or_int",
            ),
            rx.text((VarOperationState.int_var1 > VarOperationState.int_var2).to_string(), id="int_gt_int"),
            rx.text((VarOperationState.int_var1 < VarOperationState.int_var2).to_string(), id="int_lt_int"),
            rx.text((VarOperationState.int_var1 >= VarOperationState.int_var2).to_string(), id="int_gte_int"),
            rx.text((VarOperationState.int_var1 <= VarOperationState.int_var2).to_string(), id="int_lte_int"),
            rx.text(VarOperationState.int_var1 ^ VarOperationState.int_var2, id="int_xor_int"),
            rx.text(VarOperationState.int_var1 << VarOperationState.int_var2, id="int_lshift_int"),
            rx.text(VarOperationState.int_var1 >> VarOperationState.int_var2, id="int_rshift_int"),
            rx.text(VarOperationState.int_var1 & VarOperationState.int_var2, id="int_and_int"),
            rx.text((VarOperationState.int_var1 == VarOperationState.int_var2).to_string(), id="int_eq_int"),
            rx.text((VarOperationState.int_var1 != VarOperationState.int_var2).to_string(), id="int_neq_int"),

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
                VarOperationState.float_var1 ** VarOperationState.int_var2,
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
            rx.text(VarOperationState.float_var1 % VarOperationState.int_var2, id="float_mod_int"),
            rx.text((VarOperationState.float_var1 > VarOperationState.int_var2).to_string(), id="float_gt_int"),
            rx.text((VarOperationState.float_var1 < VarOperationState.int_var2).to_string(), id="float_lt_int"),
            rx.text((VarOperationState.float_var1 >= VarOperationState.int_var2).to_string(), id="float_gte_int"),
            rx.text((VarOperationState.float_var1 <= VarOperationState.int_var2).to_string(), id="float_lte_int"),
            rx.text((VarOperationState.float_var1 == VarOperationState.int_var2).to_string(), id="float_eq_int"),
            rx.text((VarOperationState.float_var1 != VarOperationState.int_var2).to_string(), id="float_neq_int"),

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
                VarOperationState.float_var1 ** VarOperationState.float_var2,
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
            rx.text(VarOperationState.float_var1 % VarOperationState.float_var2, id="float_mod_float"),
            rx.text((VarOperationState.float_var1 > VarOperationState.float_var2).to_string(), id="float_gt_float"),
            rx.text((VarOperationState.float_var1 < VarOperationState.float_var2).to_string(), id="float_lt_float"),
            rx.text((VarOperationState.float_var1 >= VarOperationState.float_var2).to_string(), id="float_gte_float"),
            rx.text((VarOperationState.float_var1 <= VarOperationState.float_var2).to_string(), id="float_lte_float"),
            rx.text((VarOperationState.float_var1 == VarOperationState.float_var2).to_string(), id="float_eq_float"),
            rx.text((VarOperationState.float_var1 != VarOperationState.float_var2).to_string(), id="float_neq_float"),

            # STR STR
            rx.text(
                VarOperationState.str_var1 + VarOperationState.str_var2,
                id="str_add_str",
            ),
            rx.text((VarOperationState.str_var1 > VarOperationState.str_var2).to_string(), id="str_gt_str"),
            rx.text((VarOperationState.str_var1 < VarOperationState.str_var2).to_string(), id="str_lt_str"),
            rx.text((VarOperationState.str_var1 >= VarOperationState.str_var2).to_string(), id="str_gte_str"),
            rx.text((VarOperationState.str_var1 <= VarOperationState.str_var2).to_string(), id="str_lte_str"),
            rx.text((VarOperationState.float_var1 == VarOperationState.float_var2).to_string(), id="str_eq_str"),
            rx.text((VarOperationState.float_var1 != VarOperationState.float_var2).to_string(), id="str_neq_str"),

            # STR, INT
            rx.text(VarOperationState.str_var1 * VarOperationState.int_var2, id="str_mult_int"),

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
                VarOperationState.float_var1 ** VarOperationState.float_var2,
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
            rx.text(VarOperationState.float_var1 % VarOperationState.float_var2, id="float_mod_float"),
            rx.text((VarOperationState.float_var1 > VarOperationState.float_var2).to_string(), id="float_gt_float"),
            rx.text((VarOperationState.float_var1 < VarOperationState.float_var2).to_string(), id="float_lt_float"),
            rx.text((VarOperationState.float_var1 >= VarOperationState.float_var2).to_string(), id="float_gte_float"),
            rx.text((VarOperationState.float_var1 <= VarOperationState.float_var2).to_string(), id="float_lte_float"),
            rx.text((VarOperationState.float_var1 == VarOperationState.float_var2).to_string(), id="float_eq_float"),
            rx.text((VarOperationState.float_var1 != VarOperationState.float_var2).to_string(), id="float_neq_float"),

            # LIST, LIST
            rx.text(
                (VarOperationState.list1 + VarOperationState.list2).to_string(),
                id="list_add_list",
            ),
            rx.text(VarOperationState.list1 & VarOperationState.list2, id="list_and_list"),
            rx.text(VarOperationState.list1 | VarOperationState.list2, id="list_or_list"),
            rx.text((VarOperationState.float_var1 > VarOperationState.float_var2).to_string(), id="list_gt_list"),
            rx.text((VarOperationState.float_var1 < VarOperationState.float_var2).to_string(), id="list_lt_list"),
            rx.text((VarOperationState.float_var1 >= VarOperationState.float_var2).to_string(), id="list_gte_list"),
            rx.text((VarOperationState.float_var1 <= VarOperationState.float_var2).to_string(), id="list_lte_list"),
            rx.text((VarOperationState.float_var1 == VarOperationState.float_var2).to_string(), id="list_eq_list"),
            rx.text((VarOperationState.float_var1 != VarOperationState.float_var2).to_string(), id="list_neq_list"),

            # LIST, INT
            rx.text(VarOperationState.list1 * VarOperationState.int_var2, id="list_mult_int"),
        )


    app.compile()


@pytest.fixture(scope="session")
def var_operations(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start FormSubmit app at tmp_path via AppHarness.

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
    """GEt an instance of the browser open to the form_submit app.

    Args:
        form_submit: harness for ServerSideEvent app

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
    assert var_operations.app_instance is not None, "app is not running"

    assert driver.find_element(By.ID, "int_add_int").text == "15"
    assert driver.find_element(By.ID, "int_mult_int").text == "50"
    assert driver.find_element(By.ID, "int_sub_int").text == "5"
    assert driver.find_element(By.ID, "int_exp_int").text == "100000"
    assert driver.find_element(By.ID, "int_div_int").text == "2"
    assert driver.find_element(By.ID, "int_floor_int").text == "1"
    assert driver.find_element(By.ID, "int_xand_int").text == "10"
