import boa
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import timedelta

SETTINGS = dict(max_examples=2000, deadline=timedelta(seconds=1000))
LN_2 = 693147180559945344


def _exp_input(power):
    return -1 * LN_2 * power / 10**18


@given(st.integers(min_value=0, max_value=2**256 - 1))
@settings(**SETTINGS)
def test_halfpow(tricrypto_swap, power):

    # there's a raise in the halfpow for very large input values,
    # so catch that first:
    if int(_exp_input(power)) >= 135305999368893231589:
        with pytest.raises(boa.contract.BoaError):
            tricrypto_swap.eval(f"self.halfpow({power})")

    # compare halfpow:
    pow_int = tricrypto_swap.eval(f"self.halfpow({power})") / 1e18
    pow_ideal = 0.5 ** (power / 1e18)
    assert abs(pow_int - pow_ideal) < max(5 * 1e10 / 1e18, 5e-16)
    assert pow_int == pytest.approx(pow_ideal)
