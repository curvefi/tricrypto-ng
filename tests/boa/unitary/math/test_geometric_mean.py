import typing

from boa.test import strategy
from hypothesis import given, settings
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=10000,
    deadline=None,
)
MAX_VAL = SizeLimits.MAX_UINT256 / 10**18


def geometric_mean_int(x: typing.List[int]) -> int:
    """for 3 element arrays only"""
    return int((x[0] * x[1] * x[2]) ** (1 / 3))


@given(
    x=strategy("uint256[3]", min_value=10**18, max_value=10**9 * 10**18),
)
@settings(**SETTINGS)
def test_geometric_mean(math_optimized, x):
    val = math_optimized.geometric_mean(x)
    assert val > 0
    diff = abs(geometric_mean_int(x) - val)
    assert diff / val <= max(1e-10, 1 / min(x))


@given(
    x=strategy("uint256[3]", min_value=10**18, max_value=10**9 * 10**18),
)
@settings(**SETTINGS)
def test_compare_geometric_mean(math_optimized, math_unoptimized, x):
    val_optimized_math = math_optimized.geometric_mean(x)
    val_unoptimized_math = math_unoptimized.geometric_mean(x)
    diff = abs(val_optimized_math - val_unoptimized_math)
    assert diff / val_optimized_math <= max(1e-10, 1 / min(x))
