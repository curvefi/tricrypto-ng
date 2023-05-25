import random

import boa
import pytest

from tests.boa.utils.tokens import mint_for_testing

NUM_RUNS = 100


def _choose_indices():
    i = random.randint(0, 2)
    j = random.choice([k for k in range(0, 2) if k not in [i]])
    return i, j


def _random_exchange(swap):

    i, j = _choose_indices()
    amount = int(swap.balances(i) * 0.01)

    use_eth = i == 2
    value = 0
    if use_eth:
        value = amount

    swap.exchange(i, j, amount, 0, use_eth, value=value)
    boa.env.time_travel(random.randint(12, 600))


def _random_deposit(swap):

    balances = [swap.balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]

    swap.add_liquidity(amounts, 0, True, value=amounts[2])

    boa.env.time_travel(random.randint(12, 600))
    

def _random_deposit_weth(swap):

    balances = [swap.balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]
    swap.add_liquidity(amounts, 0, False)
    boa.env.time_travel(random.randint(12, 600))


def _random_deposit_one(swap):
    balances = [swap.balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    # i = random.randint(0, 2)
    i = 2
    use_eth = i == 2
    amounts = [0, 0, 0]
    value = 0
    for j in range(3):
        if i == j:
            amounts[i] = int(balances[i] * c)
            if use_eth:
                value = amounts[i]

    # swap.add_liquidity(amounts, 0, use_eth, value=value)
    swap.add_liquidity(amounts, 0, False)
        
    boa.env.time_travel(random.randint(12, 600))


def _random_proportional_withdraw(swap):

    amount = int(swap.totalSupply() * random.uniform(0, 0.01))

    swap.remove_liquidity(amount, [0, 0, 0], True)

    boa.env.time_travel(random.randint(12, 600))


def _random_withdraw_one(swap):

    i = random.randint(0, 2)
    amount = int(swap.totalSupply() * 0.01)
    use_eth = i == 2

    swap.remove_liquidity_one_coin(amount, i, 0, use_eth)


# @pytest.mark.skip
# @pytest.mark.profile
def test_profile_amms(swap_with_deposit, coins, user, math_contract):

    swap = swap_with_deposit

    for coin in coins:
        mint_for_testing(coin, user, 10**50)
        coin.approve(swap, 2**256 - 1)

    boa.env.set_balance(user, 10**50)

    with boa.env.prank(user):
        
        for k in range(NUM_RUNS):

            # deposit:
            _random_deposit(swap)
            
            # deposit with weth:
            _random_deposit_weth(swap)

            # deposit single token:
            # _random_deposit_one(swap)

            # swap:
            _random_exchange(swap)

            # withdraw proportionally:
            _random_proportional_withdraw(swap)

            # withdraw in one coin:
            _random_withdraw_one(swap)
