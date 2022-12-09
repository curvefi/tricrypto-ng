import pytest
from boa.test import strategy
from hypothesis import given, settings


@given(strategy("uint256", min_value=0, max_value=2**256 - 1))
@settings(max_examples=10000, deadline=None)
def test_halfpow(math_unoptimized, power):

    # compare halfpow:
    pow_int = math_unoptimized.halfpow(power, 10**10) / 1e18
    pow_ideal = 0.5 ** (power / 1e18)
    assert abs(pow_int - pow_ideal) < max(5 * 1e10 / 1e18, 5e-16)
    assert pow_int == pytest.approx(pow_ideal)
