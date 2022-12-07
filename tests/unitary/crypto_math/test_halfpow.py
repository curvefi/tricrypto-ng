import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings


def _exp_input(power):
    return -1 * 693147180559945344 * power / 10**18


@given(strategy("uint256", min_value=0, max_value=2**256 - 1))
@settings(max_examples=10000, deadline=None)
def test_halfpow(math_optimized, power):

    # there's a raise in the halfpow for very large input values,
    # so catch that first:
    if int(_exp_input(power)) >= 135305999368893231589:
        with boa.reverts("exp overflow"):
            math_optimized.halfpow(power)

    # compare halfpow:
    pow_int = math_optimized.halfpow(power) / 1e18
    pow_ideal = 0.5 ** (power / 1e18)
    assert abs(pow_int - pow_ideal) < max(5 * 1e10 / 1e18, 5e-16)
    assert pow_int == pytest.approx(pow_ideal)


@given(strategy("uint256", min_value=0, max_value=2**256 - 1))
@settings(max_examples=10000, deadline=None)
def test_compare_halfpow(math_optimized, math_unoptimized, power):

    # there's a raise in the halfpow for very large input values,
    # so catch that first:
    if int(_exp_input(power)) >= 135305999368893231589:
        with boa.reverts("exp overflow"):
            math_optimized.halfpow(power)

    # compare halfpow:
    pow_int_optimized = math_optimized.halfpow(power)
    pow_int_unoptimized = math_unoptimized.halfpow(power, 10**10)
    assert abs(pow_int_optimized - pow_int_unoptimized) <= 10**10
