import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings  # noqa

from tests.conftest import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}


@given(
    value=strategy(
        "uint256", min_value=10**16, max_value=10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile_calls
def test_deposit_swap2(
    swap2,
    coins,
    user,
    value,
    i,
):
    amounts = [0] * 3
    amounts[i] = value * 10**18 // ([10**18] + INITIAL_PRICES)[i]
    mint_for_testing(coins[i], user, amounts[i])
    with boa.env.prank(user):
        swap2.add_liquidity(amounts, 0)


@given(
    value=strategy(
        "uint256", min_value=10**16, max_value=10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile_calls
def test_deposit_swap3(
    swap3,
    coins,
    user,
    value,
    i,
):
    amounts = [0] * 3
    amounts[i] = value * 10**18 // ([10**18] + INITIAL_PRICES)[i]
    mint_for_testing(coins[i], user, amounts[i])
    with boa.env.prank(user):
        swap3.add_liquidity(amounts, 0)
