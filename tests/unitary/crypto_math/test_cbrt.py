from datetime import timedelta

import boa
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256
MAX_CBRT_VAL = MAX_VAL // 10**36


@pytest.fixture(scope="module")
def cbrt_1e18_base():
    def _impl(x: int) -> int:
        # x is taken at base 1e36
        # result is at base 1e18

        # avoid division by error problem:
        if x == 0:
            return 0

        # xx = x * 10**18
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


def test_cbrt_python_1e18_input(cbrt_1e18_base):
    val = 9000000000000000000
    assert cbrt_1e18_base(val) == 3000000000000000000


def test_cbrt_1e18_input(tricrypto_math):
    val = 10**18
    assert tricrypto_math.eval(f"self.cbrt({val})") == val


@given(val=st.integers(min_value=0, max_value=MAX_CBRT_VAL - 1))
@settings(max_examples=20000, deadline=timedelta(seconds=1000))
@example(0)
@example(1)
def test_cbrt_exact(tricrypto_math, cbrt_1e18_base, val):

    cbrt_python = cbrt_1e18_base(val)
    cbrt_vyper = tricrypto_math.eval(f"self.cbrt({val})")

    try:
        assert cbrt_python == cbrt_vyper
    except AssertionError:
        assert abs(cbrt_python - cbrt_vyper) == 1
        pytest.warn(f"cbrt_python != cbrt_vyper for val = {val}")


@given(val=st.integers(min_value=MAX_CBRT_VAL, max_value=MAX_VAL))
@settings(max_examples=1000, deadline=timedelta(seconds=1000))
@example(MAX_VAL)
@example(MAX_CBRT_VAL)
def test_cbrt_revert_gte_limit(tricrypto_math, val):

    with boa.reverts("inaccurate cbrt"):
        tricrypto_math.eval(f"self.cbrt({val})")
        assert True
