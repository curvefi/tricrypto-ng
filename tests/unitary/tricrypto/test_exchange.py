import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings  # noqa

from tests.conftest import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 100, "deadline": None}


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=3),
    j=strategy("uint", min_value=0, max_value=3),
)
@settings(**SETTINGS)
def test_exchange_all(tricrypto_swap_with_deposit, coins, user, amount, i, j):

    if i == j or i > 2 or j > 2:
        with boa.reverts():
            tricrypto_swap_with_deposit.get_dy(i, j, 10**6)
        with boa.reverts(), boa.env.prank(user):
            tricrypto_swap_with_deposit.exchange(i, j, 10**6, 0)

    else:
        prices = [10**18] + INITIAL_PRICES
        amount = amount * 10**18 // prices[i]
        mint_for_testing(coins[i], user, amount)

        calculated = tricrypto_swap_with_deposit.get_dy(i, j, amount)
        measured_i = coins[i].balanceOf(user)
        measured_j = coins[j].balanceOf(user)
        d_balance_i = tricrypto_swap_with_deposit.balances(i)
        d_balance_j = tricrypto_swap_with_deposit.balances(j)

        with boa.env.prank(user):
            tricrypto_swap_with_deposit.exchange(
                i, j, amount, int(0.999 * calculated)
            )

        measured_i -= coins[i].balanceOf(user)
        measured_j = coins[j].balanceOf(user) - measured_j
        d_balance_i = tricrypto_swap_with_deposit.balances(i) - d_balance_i
        d_balance_j = tricrypto_swap_with_deposit.balances(j) - d_balance_j

        assert amount == measured_i
        assert calculated == measured_j

        assert d_balance_i == amount
        assert -d_balance_j == measured_j


@pytest.mark.parametrize("j", [0, 1])
@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    )
)
@settings(**SETTINGS)
def test_exchange_from_eth(
    tricrypto_swap_with_deposit, coins, user, amount, j
):

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[2]

    calculated = tricrypto_swap_with_deposit.get_dy(2, j, amount)
    measured_i = boa.env.get_balance(user)
    measured_j = coins[j].balanceOf(user)
    d_balance_i = tricrypto_swap_with_deposit.balances(2)
    d_balance_j = tricrypto_swap_with_deposit.balances(j)

    with boa.env.prank(user):
        tricrypto_swap_with_deposit.exchange(
            2, j, amount, int(0.999 * calculated), True, value=amount
        )

    measured_i -= boa.env.get_balance(user)
    measured_j = coins[j].balanceOf(user) - measured_j
    d_balance_i = tricrypto_swap_with_deposit.balances(2) - d_balance_i
    d_balance_j = tricrypto_swap_with_deposit.balances(j) - d_balance_j

    assert amount == measured_i
    assert calculated == measured_j

    assert d_balance_i == amount
    assert -d_balance_j == measured_j


@pytest.mark.parametrize("i", [0, 1])
@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    )
)
@settings(**SETTINGS)
def test_exchange_into_eth(
    tricrypto_swap_with_deposit, coins, user, amount, i
):

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)

    calculated = tricrypto_swap_with_deposit.get_dy(i, 2, amount)
    measured_i = coins[i].balanceOf(user)
    measured_j = boa.env.get_balance(user)
    d_balance_i = tricrypto_swap_with_deposit.balances(i)
    d_balance_j = tricrypto_swap_with_deposit.balances(2)

    with boa.env.prank(user):
        tricrypto_swap_with_deposit.exchange(
            i, 2, amount, int(0.999 * calculated), True
        )

    measured_i -= coins[i].balanceOf(user)
    measured_j = boa.env.get_balance(user) - measured_j
    d_balance_i = tricrypto_swap_with_deposit.balances(i) - d_balance_i
    d_balance_j = tricrypto_swap_with_deposit.balances(2) - d_balance_j

    assert amount == measured_i
    assert calculated == measured_j

    assert d_balance_i == amount
    assert -d_balance_j == measured_j


@pytest.mark.parametrize("j", [0, 1])
@pytest.mark.parametrize("modifier", [0, 1.01, 2])
def test_incorrect_eth_amount(tricrypto_swap_with_deposit, user, j, modifier):
    amount = 10**18
    with boa.reverts(dev="incorrect eth amount"), boa.env.prank(user):
        tricrypto_swap_with_deposit.exchange(
            2, j, amount, 0, True, value=int(amount * modifier)
        )


@pytest.mark.parametrize("j", [0, 1])
def test_send_eth_without_use_eth(tricrypto_swap_with_deposit, user, j):
    amount = 10**18
    with boa.reverts(dev="nonzero eth amount"), boa.env.prank(user):
        tricrypto_swap_with_deposit.exchange(
            2, j, amount, 0, False, value=amount
        )


@pytest.mark.parametrize("i", [0, 1])
def test_send_eth_with_incorrect_i(tricrypto_swap_with_deposit, user, i):
    amount = 10**18
    with boa.reverts(dev="nonzero eth amount"), boa.env.prank(user):
        tricrypto_swap_with_deposit.exchange(
            i, 2, amount, 0, True, value=amount
        )
