import pytest
from boa.test import strategy
from hypothesis import example, given, settings
from vyper.utils import SizeLimits

SETTINGS = {"max_examples": 10000, "deadline": None}
MAX_VAL = SizeLimits.MAX_UINT256
MAX_CBRT_PRECISE_VAL = MAX_VAL // 10**36


def test_cbrt_expected_output(cbrt_1e18_base, math_optimized):
    vals = [9 * 10**18, 8 * 10**18, 10**18, 1]
    correct_cbrts = [2080083823051904114, 2 * 10**18, 10**18, 10**12]
    for ix, val in enumerate(vals):
        assert math_optimized.internal.cbrt(val) == correct_cbrts[ix]
        assert cbrt_1e18_base(val) == correct_cbrts[ix]


@given(
    val=strategy("uint256", min_value=0, max_value=MAX_CBRT_PRECISE_VAL - 1)
)
@settings(**SETTINGS)
@example(0)
@example(1)
def test_cbrt_exact(math_optimized, cbrt_1e18_base, val):

    cbrt_python = cbrt_1e18_base(val)
    cbrt_vyper = math_optimized.internal.cbrt(val)

    try:
        assert cbrt_python == cbrt_vyper
    except AssertionError:
        assert abs(cbrt_python - cbrt_vyper) == 1
        pytest.warn(f"cbrt_python != cbrt_vyper for val = {val}")


@given(
    val=strategy("uint256", min_value=MAX_CBRT_PRECISE_VAL, max_value=MAX_VAL)
)
@settings(**SETTINGS)
@example(MAX_VAL)
@example(MAX_CBRT_PRECISE_VAL)
def test_cbrt_precision_loss_gte_limit(cbrt_1e18_base, math_optimized, val):

    cbrt_vyper = math_optimized.internal.cbrt(val)
    cbrt_python = cbrt_1e18_base(val)

    assert cbrt_vyper != cbrt_python
    assert cbrt_vyper == pytest.approx(cbrt_python)
