from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import timedelta

SETTINGS = dict(max_examples=2000, deadline=timedelta(seconds=1000))


@given(st.integers(min_value=0, max_value=2**256 - 1))
@settings(**SETTINGS)
def test_halfpow(tricrypto_swap, power):
    pow_int = tricrypto_swap.halfpow(power) / 1e18
    pow_ideal = 0.5 ** (power / 1e18)
    assert abs(pow_int - pow_ideal) < max(5 * 1e10 / 1e18, 5e-16)
