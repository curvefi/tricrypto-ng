from datetime import timedelta

from gmpy2 import iroot, mpz
from hypothesis import given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

CBRT_SETTINGS = dict(max_examples=10000, deadline=timedelta(seconds=1000))
MAX_VAL = SizeLimits.MAX_UINT256
SQRT_MAX_VAL = int(iroot(mpz(MAX_VAL, 2))[0])


st.composite


def cbrt_inputs(draw, max_val=MAX_VAL):

    full_range = st.integers(min_value=0, max_value=max_val)
    binary_exponent_range = st.integers(min_value=0, max_value=255).map(
        lambda x: 2**x
    )

    return draw(st.one_of(full_range, binary_exponent_range))


@given(val=cbrt_inputs(max_val=10**18))
@settings(**CBRT_SETTINGS)
def test_cbrt_exact(tricrypto_math, val):

    cbrt_ideal = iroot(mpz(val), 3)[0]
    cbrt_int = tricrypto_math.eval(f"self.cbrt({val})")
    assert cbrt_int == cbrt_ideal
