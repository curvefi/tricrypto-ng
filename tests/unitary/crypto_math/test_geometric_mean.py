import typing
from datetime import timedelta

from gmpy2 import mpz, root
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=20000,
    deadline=timedelta(seconds=1000),
)
MAX_VAL = SizeLimits.MAX_UINT256 / 10**18


def geometric_mean_int(x: typing.List[int]) -> int:
    """for 3 element arrays only"""

    x = [mpz(i) for i in x]
    return int(root(x[0] * x[1] * x[2], 3))


@given(
    x0=st.integers(min_value=10**9, max_value=10**9 * 10**18),
    x1=st.integers(min_value=10**9, max_value=10**9 * 10**18),
    x2=st.integers(min_value=10**9, max_value=10**9 * 10**18),
)
@settings(**SETTINGS)
def test_geometric_mean(tricrypto_math, x0, x1, x2):
    val = tricrypto_math.geometric_mean([x0, x1, x2])
    assert val > 0
    diff = abs(geometric_mean_int([x0, x1, x2]) - val)
    assert diff / val <= max(1e-10, 1 / min([x0, x1, x2]))
