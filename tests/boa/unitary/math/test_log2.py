import math

from boa.test import strategy
from hypothesis import given, settings
from vyper.utils import SizeLimits


@given(
    strategy(
        "uint256",
        min_value=0,
        max_value=SizeLimits.MAX_UINT256,
    )
)
@settings(max_examples=10000, deadline=None)
def test_log2(math_optimized, x):

    if x == 0:
        assert math_optimized.internal._snekmate_log_2(x, False) == 0
        return

    log2_ideal = int(math.log2(x))
    log2_implementation = math_optimized.internal._snekmate_log_2(x, False)

    try:
        assert log2_ideal == log2_implementation
    except:  # noqa: E722; there will be off-by-one cases
        assert abs(log2_ideal - log2_implementation) == 1
