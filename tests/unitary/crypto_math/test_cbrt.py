from datetime import timedelta

import boa
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256
MAX_CBRT_VAL = MAX_VAL // 10**36


def test_cbrt_expected_output(cbrt_1e18_base, tricrypto_math):
    vals = [9 * 10**18, 8 * 10**18, 10**18, 1]
    correct_cbrts = [2080083823051904114, 2 * 10**18, 10**18, 10**12]
    for ix, val in enumerate(vals):
        assert tricrypto_math.eval(f"self.cbrt({val})") == correct_cbrts[ix]
        assert cbrt_1e18_base(val) == correct_cbrts[ix]


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
