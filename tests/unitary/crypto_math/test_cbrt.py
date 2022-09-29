from datetime import timedelta

import boa
import pytest
from gmpy2 import iroot, mpz
from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=20000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256
CBRT_PRECISION = 10**18


@given(val=st.integers(min_value=0, max_value=MAX_VAL))
@settings(**CBRT_SETTINGS)
@example(0)
@example(MAX_VAL)
@example(1)
@example(CBRT_PRECISION)
def test_cbrt(tricrypto_math, val):

    cbrt_gmpy2 = iroot(mpz(val) * CBRT_PRECISION, 3)[0]

    if val >= 10**59:
        with boa.reverts("inaccurate cbrt"):
            tricrypto_math.eval(f"self.cbrt({val})")
    else:
        cbrt_vyper = tricrypto_math.eval(f"self.cbrt({val})")
        assert cbrt_gmpy2 == pytest.approx(cbrt_vyper)
