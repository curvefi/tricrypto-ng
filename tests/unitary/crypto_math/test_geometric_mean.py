import typing

from boa.test import strategy
from gmpy2 import mpz, root
from hypothesis import given, settings
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=10000,
    deadline=None,
)
MAX_VAL = SizeLimits.MAX_UINT256 / 10**18


def geometric_mean_int(x: typing.List[int]) -> int:
    """for 3 element arrays only"""

    x = [mpz(i) for i in x]
    return int(root(x[0] * x[1] * x[2], 3))


@given(
    x=strategy("uint256[3]", min_value=10**9, max_value=10**9 * 10**18),
)
@settings(**SETTINGS)
def test_geometric_mean(tricrypto_math, x):
    val = tricrypto_math.geometric_mean(x)
    assert val > 0
    diff = abs(geometric_mean_int(x) - val)
    assert diff / val <= max(1e-10, 1 / min(x))
