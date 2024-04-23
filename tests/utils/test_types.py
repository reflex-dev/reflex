from typing import Literal

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
