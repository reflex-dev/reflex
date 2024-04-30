from typing import Any, List, Literal, Tuple, Union

import pytest

from reflex.utils import types


@pytest.mark.parametrize(
    "params, allowed_value_str, value_str",
    [
        (["size", 1, Literal["1", "2", "3"], "Heading"], "'1','2','3'", "1"),
        (["size", "1", Literal[1, 2, 3], "Heading"], "1,2,3", "'1'"),
    ],
)
def test_validate_literal_error_msg(params, allowed_value_str, value_str):
    with pytest.raises(ValueError) as err:
        types.validate_literal(*params)

    assert (
        err.value.args[0] == f"prop value for {str(params[0])} of the `{params[-1]}` "
        f"component should be one of the following: {allowed_value_str}. Got {value_str} instead"
    )


@pytest.mark.parametrize(
    "cls,cls_check,expected",
    [
        (int, Any, True),
        (Tuple[int], Any, True),
        (List[int], Any, True),
        (int, int, True),
        (int, object, True),
        (int, Union[int, str], True),
        (int, Union[str, int], True),
        (str, Union[str, int], True),
        (str, Union[int, str], True),
        (int, Union[str, float, int], True),
        (int, Union[str, float], False),
        (int, Union[float, str], False),
        (int, str, False),
        (int, List[int], False),
    ],
)
def test_issubclass(
    cls: types.GenericType, cls_check: types.GenericType, expected: bool
) -> None:
    assert types._issubclass(cls, cls_check) == expected
