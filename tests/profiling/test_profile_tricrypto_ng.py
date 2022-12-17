import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings  # noqa

from tests.conftest import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}

@pytest.fixture(scope="module")
def swap(tricrypto_swap_with_deposit, optimized):
    name = "TricryptoSwap"
    if optimized:
        name += "Optimized"
    tricrypto_swap_with_deposit.compiler_data.contract_name = name
    return tricrypto_swap_with_deposit


@pytest.fixture(scope="module")
def views(tricrypto_views, optimized):
    name = "TricryptoViews"
    if optimized:
        name += "Optimized"
    tricrypto_views.compiler_data.contract_name = name
    return tricrypto_views


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile_calls
def test_profile_exchange(
    swap, 
    views,
    coins,
    user,
    amount,
    i,
    j, 
    optimized
):
    
    if i == j:
        return
    
    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)

    if not optimized:
        calculated = swap.get_dy(i, j, amount)
    else:
        calculated = views.get_dy(i, j, amount)

    with boa.env.prank(user):
        swap.exchange(
            i, j, amount, int(0.999 * calculated)
        )
