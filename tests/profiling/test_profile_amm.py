import random

import boa
import pytest

from tests.utils.tokens import mint_for_testing

NUM_RUNS = 100


def _choose_indices():
    i = random.randint(0, 2)
    j = random.choice([k for k in range(0, 2) if k not in [i]])
    return i, j


def _random_exchange(swaps):

    i, j = _choose_indices()
    amount = int(swaps[0].balances(i) * 0.01)

    use_eth = i == 2
    value = 0
    if use_eth:
        value = amount

    for swap in swaps:
        swap.exchange(i, j, amount, 0, use_eth, value=value)

    boa.env.time_travel(random.randint(12, 600))


def _random_deposit(swaps):

    balances = [swaps[0].balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]

    swaps[0].add_liquidity(amounts, 0, True, value=amounts[2])
    swaps[1].add_liquidity(amounts, 0)

    boa.env.time_travel(random.randint(12, 600))


def _random_deposit_one(swaps):
    balances = [swaps[0].balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    i = random.randint(0, 2)
    use_eth = i == 2
    amounts = [0, 0, 0]
    value = 0
    for j in range(3):
        if i == j:
            amounts[i] = int(balances[i] * c)
            if use_eth:
                value = amounts[i]

    swaps[0].add_liquidity(amounts, 0, use_eth, value=value)
    swaps[1].add_liquidity(amounts, 0)

    boa.env.time_travel(random.randint(12, 600))


def _random_proportional_withdraw(swaps, total_supply):

    amount = int(total_supply * random.uniform(0, 0.01))

    swaps[0].remove_liquidity(amount, [0, 0, 0], True)
    swaps[1].remove_liquidity(amount, [0, 0, 0])

    boa.env.time_travel(random.randint(12, 600))


def _random_withdraw_one(swaps, total_supply):

    i = random.randint(0, 2)
    amount = int(total_supply * 0.01)
    use_eth = i == 2

    swaps[0].remove_liquidity_one_coin(amount, i, 0, use_eth)
    swaps[1].remove_liquidity_one_coin(amount, i, 0)


# @pytest.mark.skip
@pytest.mark.profile
def test_profile_amms(swap_legacy, swap_with_deposit, coins, user):

    swaps = [swap_with_deposit, swap_legacy]

    for coin in coins:
        mint_for_testing(coin, user, 10**50)
        for swap in swaps:
            coin.approve(swap, 2**256 - 1)

    boa.env.set_balance(user, 10**50)

    with boa.env.prank(user):
        for k in range(NUM_RUNS):

            # deposit:
            _random_deposit(swaps)

            # deposit single token:
            _random_deposit_one(swaps)

            # swap:
            _random_exchange(swaps)

            # withdraw proportionally:
            _random_proportional_withdraw(
                swaps, swap_with_deposit.totalSupply()
            )

            # withdraw in one coin:
            _random_withdraw_one(swaps, swap_with_deposit.totalSupply())
