import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings  # noqa

from tests.conftest import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile_calls
def test_profile_exchange_swap2(
    swap2,
    coins,
    user,
    amount,
    i,
    j,
):

    if i == j:
        return

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)
    calculated = swap2.get_dy(i, j, amount)

    with boa.env.prank(user):
        swap2.exchange(i, j, amount, int(0.999 * calculated))


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile_calls
def test_profile_exchange_swap3(
    swap3,
    views3,
    coins,
    user,
    amount,
    i,
    j,
):

    if i == j:
        return

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)
    calculated = views3.get_dy(i, j, amount)

    with boa.env.prank(user):
        swap3.exchange(i, j, amount, int(0.999 * calculated))
