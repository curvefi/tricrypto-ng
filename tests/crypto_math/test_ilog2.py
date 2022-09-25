import math
from datetime import timedelta

import boa
from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

ILOG2_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256


@given(st.integers(min_value=0, max_value=MAX_VAL))
@settings(**ILOG2_SETTINGS)
@example(SizeLimits.MAX_UINT256)
@example(0)
@example(1)
def test_ilog2(tricrypto_math, val):

    if not val == 0:

        ilog2_ideal = int(math.log(val, 2))
        ilog2_int = tricrypto_math.eval(f"self.ilog2({val})")

        # TODO: why is this not exact?
        assert ilog2_int - ilog2_ideal <= 1

    else:

        with boa.reverts("undefined"):
            tricrypto_math.eval(f"self.ilog2({val})")
