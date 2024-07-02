"""Specialized test for a larger state tree."""

import asyncio
from typing import Generator

import pytest

import reflex as rx
from reflex.state import BaseState, StateManager, StateManagerRedis, _substate_key


class Root(BaseState):
    """Root of the state tree."""

    root: int


class TreeA(Root):
    """TreeA is a child of Root."""

    a: int


class SubA_A(TreeA):
    """SubA_A is a child of TreeA."""

    sub_a_a: int


class SubA_A_A(SubA_A):
    """SubA_A_A is a child of SubA_A."""

    sub_a_a_a: int


class SubA_A_A_A(SubA_A_A):
    """SubA_A_A_A is a child of SubA_A_A."""

    sub_a_a_a_a: int


class SubA_A_A_B(SubA_A_A):
    """SubA_A_A_B is a child of SubA_A_A."""

    @rx.var(cache=True)
    def sub_a_a_a_cached(self) -> int:
        """A cached var.

        Returns:
            The value of sub_a_a_a + 1
        """
        return self.sub_a_a_a + 1


class SubA_A_A_C(SubA_A_A):
    """SubA_A_A_C is a child of SubA_A_A."""

    sub_a_a_a_c: int


class SubA_A_B(SubA_A):
    """SubA_A_B is a child of SubA_A."""

    sub_a_a_b: int


class SubA_B(TreeA):
    """SubA_B is a child of TreeA."""

    sub_a_b: int


class TreeB(Root):
    """TreeB is a child of Root."""

    b: int


class SubB_A(TreeB):
    """SubB_A is a child of TreeB."""

    sub_b_a: int


class SubB_B(TreeB):
    """SubB_B is a child of TreeB."""

    sub_b_b: int


class SubB_C(TreeB):
    """SubB_C is a child of TreeB."""

    sub_b_c: int


class SubB_C_A(SubB_C):
    """SubB_C_A is a child of SubB_C."""

    sub_b_c_a: int


class TreeC(Root):
    """TreeC is a child of Root."""

    c: int


class SubC_A(TreeC):
    """SubC_A is a child of TreeC."""

    sub_c_a: int


class TreeD(Root):
    """TreeD is a child of Root."""

    d: int

    @rx.var
    def d_var(self) -> int:
        """A computed var.

        Returns:
            The value of d + 1
        """
        return self.d + 1


class TreeE(Root):
    """TreeE is a child of Root."""

    e: int


class SubE_A(TreeE):
    """SubE_A is a child of TreeE."""

    sub_e_a: int


class SubE_A_A(SubE_A):
    """SubE_A_A is a child of SubE_A."""

    sub_e_a_a: int


class SubE_A_A_A(SubE_A_A):
    """SubE_A_A_A is a child of SubE_A_A."""

    sub_e_a_a_a: int


class SubE_A_A_A_A(SubE_A_A_A):
    """SubE_A_A_A_A is a child of SubE_A_A_A."""

    sub_e_a_a_a_a: int

    @rx.var
    def sub_e_a_a_a_a_var(self) -> int:
        """A computed var.

        Returns:
            The value of sub_e_a_a_a_a + 1
        """
        return self.sub_e_a_a_a + 1


class SubE_A_A_A_B(SubE_A_A_A):
    """SubE_A_A_A_B is a child of SubE_A_A_A."""

    sub_e_a_a_a_b: int


class SubE_A_A_A_C(SubE_A_A_A):
    """SubE_A_A_A_C is a child of SubE_A_A_A."""

    sub_e_a_a_a_c: int


class SubE_A_A_A_D(SubE_A_A_A):
    """SubE_A_A_A_D is a child of SubE_A_A_A."""

    sub_e_a_a_a_d: int

    @rx.var(cache=True)
    def sub_e_a_a_a_d_var(self) -> int:
        """A computed var.

        Returns:
            The value of sub_e_a_a_a_a + 1
        """
        return self.sub_e_a_a_a + 1


ALWAYS_COMPUTED_VARS = {
    TreeD.get_full_name(): {"d_var": 1},
    SubE_A_A_A_A.get_full_name(): {"sub_e_a_a_a_a_var": 1},
}

ALWAYS_COMPUTED_DICT_KEYS = [
    Root.get_full_name(),
    TreeD.get_full_name(),
    TreeE.get_full_name(),
    SubE_A.get_full_name(),
    SubE_A_A.get_full_name(),
    SubE_A_A_A.get_full_name(),
    SubE_A_A_A_A.get_full_name(),
    SubE_A_A_A_D.get_full_name(),
]


@pytest.fixture(scope="function")
def state_manager_redis(app_module_mock) -> Generator[StateManager, None, None]:
    """Instance of state manager for redis only.

    Args:
        app_module_mock: The app module mock fixture.

    Yields:
        A state manager instance
    """
    app_module_mock.app = rx.App(state=Root)
    state_manager = app_module_mock.app.state_manager

    if not isinstance(state_manager, StateManagerRedis):
        pytest.skip("Test requires redis")

    yield state_manager

    asyncio.get_event_loop().run_until_complete(state_manager.close())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("substate_cls", "exp_root_substates", "exp_root_dict_keys"),
    [
        (
            Root,
            [
                TreeA.get_name(),
                TreeB.get_name(),
                TreeC.get_name(),
                TreeD.get_name(),
                TreeE.get_name(),
            ],
            [
                TreeA.get_full_name(),
                SubA_A.get_full_name(),
                SubA_A_A.get_full_name(),
                SubA_A_A_A.get_full_name(),
                SubA_A_A_B.get_full_name(),
                SubA_A_A_C.get_full_name(),
                SubA_A_B.get_full_name(),
                SubA_B.get_full_name(),
                TreeB.get_full_name(),
                SubB_A.get_full_name(),
                SubB_B.get_full_name(),
                SubB_C.get_full_name(),
                SubB_C_A.get_full_name(),
                TreeC.get_full_name(),
                SubC_A.get_full_name(),
                SubE_A_A_A_B.get_full_name(),
                SubE_A_A_A_C.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            TreeA,
            (TreeA.get_name(), TreeD.get_name(), TreeE.get_name()),
            [
                TreeA.get_full_name(),
                SubA_A.get_full_name(),
                SubA_A_A.get_full_name(),
                SubA_A_A_A.get_full_name(),
                SubA_A_A_B.get_full_name(),
                SubA_A_A_C.get_full_name(),
                SubA_A_B.get_full_name(),
                SubA_B.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            SubA_A_A_A,
            [TreeA.get_name(), TreeD.get_name(), TreeE.get_name()],
            [
                TreeA.get_full_name(),
                SubA_A.get_full_name(),
                SubA_A_A.get_full_name(),
                SubA_A_A_A.get_full_name(),
                SubA_A_A_B.get_full_name(),  # Cached var dep
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            TreeB,
            [TreeB.get_name(), TreeD.get_name(), TreeE.get_name()],
            [
                TreeB.get_full_name(),
                SubB_A.get_full_name(),
                SubB_B.get_full_name(),
                SubB_C.get_full_name(),
                SubB_C_A.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            SubB_B,
            [TreeB.get_name(), TreeD.get_name(), TreeE.get_name()],
            [
                TreeB.get_full_name(),
                SubB_B.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            SubB_C_A,
            [TreeB.get_name(), TreeD.get_name(), TreeE.get_name()],
            [
                TreeB.get_full_name(),
                SubB_C.get_full_name(),
                SubB_C_A.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            TreeC,
            [TreeC.get_name(), TreeD.get_name(), TreeE.get_name()],
            [
                TreeC.get_full_name(),
                SubC_A.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            TreeD,
            [TreeD.get_name(), TreeE.get_name()],
            [
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
        (
            TreeE,
            [TreeE.get_name(), TreeD.get_name()],
            [
                # Extra siblings of computed var included now.
                SubE_A_A_A_B.get_full_name(),
                SubE_A_A_A_C.get_full_name(),
                *ALWAYS_COMPUTED_DICT_KEYS,
            ],
        ),
    ],
)
async def test_get_state_tree(
    state_manager_redis,
    token,
    substate_cls,
    exp_root_substates,
    exp_root_dict_keys,
):
    """Test getting state trees and assert on which branches are retrieved.

    Args:
        state_manager_redis: The state manager redis fixture.
        token: The token fixture.
        substate_cls: The substate class to retrieve.
        exp_root_substates: The expected substates of the root state.
        exp_root_dict_keys: The expected keys of the root state dict.
    """
    state = await state_manager_redis.get_state(_substate_key(token, substate_cls))
    assert isinstance(state, Root)
    assert sorted(state.substates) == sorted(exp_root_substates)

    # Only computed vars should be returned
    assert state.get_delta() == ALWAYS_COMPUTED_VARS

    # All of TreeA, TreeD, and TreeE substates should be in the dict
    assert sorted(state.dict()) == sorted(exp_root_dict_keys)
