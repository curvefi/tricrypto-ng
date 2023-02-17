from boa.test import strategy
from hypothesis import given, settings  # noqa

SETTINGS = {"max_examples": 1000, "deadline": None}


@given(
    amount_in=strategy(
        "uint256", min_value=10**20, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_get_dx(i, j, amount_in, yuge_swap, views_contract):

    if i == j:
        return

    expected_out = views_contract.get_dy(i, j, amount_in, yuge_swap)
    approx_in = views_contract.get_dx(i, j, expected_out, yuge_swap)
    perc_diff = 100 * abs(amount_in - approx_in) / amount_in

    assert perc_diff < 1
