from datetime import timedelta

import boa
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=20000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256
MAX_CBRT_VAL = 115792089237316195423570985008687907853269


@pytest.fixture(scope="module")
def cbrt_1e18_base():
    def _impl(x: int) -> int:
        # x is taken at base 1e36
        # result is at base 1e18

        if x == 0:
            return 0

        xx = x * 10**36
        D = x
        diff = 0
        for i in range(1000):
            D_prev = D

            # The following implementation has precision errors:
            # D = (2 * D + xx // D * 10**18 // D) // 3
            # this implementation is more precise:
            D = (2 * D + xx // D**2) // 3

            if D > D_prev:
                diff = D - D_prev
            else:
                diff = D_prev - D
            if diff <= 1 or diff * 10**18 < D:
                return D
        raise ValueError("Did not converge")

    return _impl


@given(val=st.integers(min_value=0, max_value=MAX_CBRT_VAL - 1))
@settings(max_examples=20000, deadline=timedelta(seconds=1000))
@example(0)
@example(1)
def test_cbrt(tricrypto_math, cbrt_1e18_base, val):

    cbrt_python = cbrt_1e18_base(val)
    cbrt_vyper = tricrypto_math.eval(f"self.cbrt({val})")

    try:
        assert cbrt_python == cbrt_vyper
    except AssertionError:
        assert abs(cbrt_python - cbrt_vyper) == 1


@given(val=st.integers(min_value=MAX_CBRT_VAL, max_value=MAX_VAL))
@settings(max_examples=1000, deadline=timedelta(seconds=1000))
@example(MAX_VAL)
@example(MAX_CBRT_VAL)
def test_cbrt_limit_raises(tricrypto_math, val):

    with boa.reverts("inaccurate cbrt"):
        tricrypto_math.eval(f"self.cbrt({val})")
        assert True
