import random

NUM_RUNS = 2


def _choose_indices():
    i = random.randint(0, 2)
    j = random.choice([k for k in range(0, 2) if k not in [i]])
    return i, j


def _random_exchange(swap, user, coins):

    i, j = _choose_indices()
    amount = int(coins[i].balanceOf(user) * 0.01)

    use_eth = i == 2
    value = 0
    if use_eth:
        value = amount

    swap.exchange(
        i,
        j,
        amount,
        0,
        use_eth,
        sender=user,
        value=value,
        gas_limit=10**7,
    )


def _random_deposit(swap, user, coins):

    c = random.uniform(0, 0.01)
    balances = [coin.balanceOf(user) for coin in coins]
    amounts = [int(c * i * random.uniform(0, 0.8)) for i in balances]

    swap.add_liquidity(
        amounts, 0, True, sender=user, value=amounts[2], gas_limit=10**7
    )


def _random_deposit_one(swap, user, coins):

    balances = [coin.balanceOf(user) for coin in coins]
    c = random.uniform(0, 0.01)
    i = random.randint(0, 2)
    use_eth = i == 2
    amounts = [0, 0, 0]
    value = 0
    for j in range(3):
        if i == j:
            amounts[i] = int(balances[i] * c)
            if use_eth:
                value = amounts[i]

    swap.add_liquidity(
        amounts, 0, use_eth, sender=user, value=value, gas_limit=10**7
    )


def _random_proportional_withdraw(swap, user):

    user_bal = swap.balanceOf(user)
    amount = int(user_bal * random.uniform(0, 0.01))

    swap.remove_liquidity(
        amount, [0, 0, 0], True, sender=user, gas_limit=10**7
    )


def _random_withdraw_one(swap, user):

    i, j = _choose_indices()
    user_bal = swap.balanceOf(user)
    amount = int(user_bal * random.uniform(0, 0.01))
    use_eth = i == 2

    swap.remove_liquidity_one_coin(
        amount, i, 0, use_eth, sender=user, gas_limit=10**7
    )


def test_profile_amms(swap, user, coins):

    for k in range(NUM_RUNS):

        # deposit:
        _random_deposit(swap, user, coins)

        # deposit single token:
        _random_deposit_one(swap, user, coins)

        # swap:
        _random_exchange(swap, user, coins)

        # withdraw proportionally:
        _random_proportional_withdraw(swap, user)

        # withdraw in one coin:
        _random_withdraw_one(swap, user)
