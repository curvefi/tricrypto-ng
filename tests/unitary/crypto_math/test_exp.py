import math

import boa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits


@given(
    st.integers(
        min_value=SizeLimits.MIN_INT256, max_value=SizeLimits.MAX_INT256
    )
)
@settings(max_examples=10000, deadline=None)
def test_exp(tricrypto_math, x):

    if x >= 135305999368893231589:
        with boa.reverts("exp overflow"):
            tricrypto_math.eval(f"self.exp({x})")

    elif x <= -42139678854452767551:
        assert tricrypto_math.eval(f"self.exp({x})") == 0

    else:

        exp_ideal = int(math.exp(x / 10**18) * 10**18)
        exp_implementation = tricrypto_math.eval(f"self.exp({x})")

        assert exp_ideal == pytest.approx(exp_implementation)
