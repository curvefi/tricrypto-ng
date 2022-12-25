import random

import boa
import pytest

from tests.utils.tokens import mint_for_testing

NUM_RUNS = 100


def _choose_indices():
    i = random.randint(0, 2)
    j = random.choice([k for k in range(0, 2) if k not in [i]])
    return i, j


def _random_exchange(user, swap, coins):

    i, j = _choose_indices()
    amount = int(swap.balances(i) * 0.01)
    mint_for_testing(coins[i], user, amount)
    swap.exchange(i, j, amount, 0)
    boa.env.time_travel(random.randint(12, 600))


def _random_deposit(user, swap, coins):

    balances = [swap.balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]

    for i in range(3):
        mint_for_testing(coins[i], user, amounts[i])

    swap.add_liquidity(amounts, 0)
    boa.env.time_travel(random.randint(12, 600))


def _random_deposit_one(user, swap, coins):
    balances = [swap.balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    i = random.randint(0, 2)
    amounts = [0, 0, 0]
    for j in range(3):
        if i == j:
            amounts[i] = int(balances[i] * c)

    mint_for_testing(coins[i], user, amounts[i])
    swap.add_liquidity(amounts, 0)
    boa.env.time_travel(random.randint(12, 600))


def _random_proportional_withdraw(swap, total_supply):

    amount = int(total_supply * random.uniform(0, 0.01))
    swap.remove_liquidity(amount, [0, 0, 0])
    boa.env.time_travel(random.randint(12, 600))


def _random_withdraw_one(swap, total_supply):

    i = random.randint(0, 2)
    amount = int(total_supply * 0.01)
    swap.remove_liquidity_one_coin(amount, i, 0)


@pytest.mark.profile
def test_profile_swap3(swap3, coins, user):

    with boa.env.prank(user):
        for k in range(NUM_RUNS):
            # deposit:
            _random_deposit(user, swap3, coins)

            # deposit single token:
            _random_deposit_one(user, swap3, coins)

            # swap:
            _random_exchange(user, swap3, coins)

            # withdraw proportionally:
            _random_proportional_withdraw(swap3, swap3.totalSupply())

            # withdraw in one coin:
            _random_withdraw_one(swap3, swap3.totalSupply())


@pytest.mark.profile
def test_profile_swap2(swap2, token2, coins, user):

    with boa.env.prank(user):
        for k in range(NUM_RUNS):
            # deposit:
            _random_deposit(user, swap2, coins)

            # deposit single token:
            _random_deposit_one(user, swap2, coins)

            # swap:
            _random_exchange(user, swap2, coins)

            # withdraw proportionally:
            _random_proportional_withdraw(swap2, token2.totalSupply())

            # withdraw in one coin:
            _random_withdraw_one(swap2, token2.totalSupply())
