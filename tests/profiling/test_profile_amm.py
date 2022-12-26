import random
import sys

import boa
import pytest
from rich.console import Console

from tests.utils.tokens import mint_for_testing

NUM_RUNS = 20
console = Console(file=sys.stdout)


def _choose_indices():
    i = random.randint(0, 2)
    j = random.choice([k for k in range(0, 2) if k not in [i]])
    return i, j


def _random_exchange(user, swaps, coins):

    i, j = _choose_indices()

    out = []
    for swap in swaps:
        amount = int(swap.balances(i) * 0.01)
        mint_for_testing(coins[i], user, amount)
        out.append((i, j, amount, swap.exchange(i, j, amount, 0)))

    boa.env.time_travel(random.randint(12, 600))
    return out


def _random_deposit(user, swaps, coins):

    balances = [swaps[0].balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]

    for i in range(3):
        mint_for_testing(coins[i], user, 2 * amounts[i])

    for swap in swaps:
        swap.add_liquidity(amounts, 0)

    boa.env.time_travel(random.randint(12, 600))


def _random_deposit_one(user, swaps, coins):
    balances = [swaps[0].balances(i) for i in range(3)]
    c = random.uniform(0, 0.05)
    i = random.randint(0, 2)
    amounts = [0, 0, 0]
    for j in range(3):
        if i == j:
            amounts[i] = int(balances[i] * c)

    mint_for_testing(coins[i], user, 2 * amounts[i])
    for swap in swaps:
        swap.add_liquidity(amounts, 0)
    boa.env.time_travel(random.randint(12, 600))


def _random_proportional_withdraw(swaps, total_supply):

    amount = int(total_supply * random.uniform(0, 0.01))
    for swap in swaps:
        swap.remove_liquidity(amount, [0, 0, 0])

    boa.env.time_travel(random.randint(12, 600))


def _random_withdraw_one(swaps, total_supply):

    i = random.randint(0, 2)
    amount = int(total_supply * 0.01)
    for swap in swaps:
        swap.remove_liquidity_one_coin(amount, i, 0)


@pytest.mark.profile
def test_profile_amms(swap2, swap3, token2, coins, user):

    swaps = [swap3, swap2]

    with boa.env.prank(user):
        for k in range(NUM_RUNS):

            # deposit:
            _random_deposit(user, swaps, coins)

            # deposit single token:
            _random_deposit_one(user, swaps, coins)

            # swap:
            out = _random_exchange(user, swaps, coins)
            console.log(
                f"\ni, j: {out[0][0]}, {out[0][1]} \n"
                f"amounts in opt, og: {out[0][2]}, {out[1][2]} \n"
                f"exchange outputs optimised, og: {out[0][3]}, {out[1][3]} \n"
                f"% input (opt-og): {100*(out[0][2] - out[1][2])/out[0][2]} \n"
                f"% output (opt-og): {100*(out[0][3] - out[1][3])/out[0][3]}"
            )

            # withdraw proportionally:
            _random_proportional_withdraw(swaps, swap3.totalSupply())

            # withdraw in one coin:
            _random_withdraw_one(swaps, swap3.totalSupply())
