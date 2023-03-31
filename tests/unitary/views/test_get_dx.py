import pytest
from boa.test import strategy
from hypothesis import given, settings

SETTINGS = {"max_examples": 100, "deadline": None}


@given(
    amount_in=strategy(
        "uint256", min_value=10**20, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_get_dx(i, j, amount_in, yuge_swap):

    if i == j:
        return

    expected_out = yuge_swap.get_dy(i, j, amount_in)
    approx_in = yuge_swap.get_dx(i, j, expected_out)

    # not accurate, but close enough:
    assert amount_in == pytest.approx(approx_in, 1e-2)
