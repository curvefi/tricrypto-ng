import math

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings
from vyper.utils import SizeLimits


@given(
    strategy(
        "int256",
        min_value=SizeLimits.MIN_INT256,
        max_value=SizeLimits.MAX_INT256,
    )
)
@settings(max_examples=10000, deadline=None)
def test_exp(math_optimized, x):

    if x >= 135305999368893231589:
        with boa.reverts("wad_exp overflow"):
            math_optimized.wad_exp(x)

    elif x <= -42139678854452767551:
        assert math_optimized.wad_exp(x) == 0

    else:

        exp_ideal = int(math.exp(x / 10**18) * 10**18)
        exp_implementation = math_optimized.wad_exp(x)
        assert exp_ideal == pytest.approx(exp_implementation)
