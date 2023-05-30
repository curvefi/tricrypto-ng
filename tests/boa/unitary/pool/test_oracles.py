from math import exp, log, log2, sqrt

import boa
from boa.test import strategy
from hypothesis import given, settings

from tests.boa.fixtures.pool import INITIAL_PRICES
from tests.boa.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision


def norm(price_oracle, price_scale):
    norm = 0
    for k in range(2):
        ratio = price_oracle[k] * 10**18 / price_scale[k]
        if ratio > 10**18:
            ratio -= 10**18
        else:
            ratio = 10**18 - ratio
        norm += ratio**2
    return sqrt(norm)


def test_initial(swap_with_deposit):
    for i in range(2):
        assert swap_with_deposit.price_scale(i) == INITIAL_PRICES[i + 1]
        assert swap_with_deposit.price_oracle(i) == INITIAL_PRICES[i + 1]


@given(
    token_frac=strategy("uint256", min_value=10**6, max_value=10**16),
    i=strategy("uint8", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_last_price_remove_liq(swap_with_deposit, user, token_frac, i):

    prices = INITIAL_PRICES
    token_amount = token_frac * swap_with_deposit.totalSupply() // 10**18

    with boa.env.prank(user):
        swap_with_deposit.remove_liquidity_one_coin(token_amount, i, 0)

    for k in [1, 2]:
        oracle_price = swap_with_deposit.last_prices(k - 1)
        assert abs(log2(oracle_price / prices[k])) < 0.1


@given(
    amount=strategy(
        "uint256", min_value=10**10, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
    t=strategy("uint256", min_value=10, max_value=10 * 86400),
)
@settings(**SETTINGS)
def test_ma(swap_with_deposit, coins, user, amount, i, j, t):
    if i == j:
        return

    prices1 = INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    rebal_params = swap_with_deposit.internal._unpack(
        swap_with_deposit._storage.packed_rebalancing_params.get()
    )
    ma_time = rebal_params[2]

    # here we dont mine because we're time travelling later
    with boa.env.prank(user):
        swap_with_deposit.exchange(i, j, amount, 0)

    prices2 = [swap_with_deposit.last_prices(k) for k in [0, 1]]

    boa.env.time_travel(t)

    with boa.env.prank(user):
        swap_with_deposit.remove_liquidity_one_coin(10**15, 0, 0)

    prices3 = [swap_with_deposit.price_oracle(k) for k in [0, 1]]

    for p1, p2, p3 in zip(prices1[1:], prices2, prices3):

        # cap new price by 2x previous price oracle value:
        new_price = min(p2, 2 * p1)

        alpha = exp(-1 * t / ma_time)
        theory = p1 * alpha + new_price * (1 - alpha)
        assert abs(log2(theory / p3)) < 0.001


# Sanity check for price scale
@given(
    amount=strategy(
        "uint256", min_value=10**10, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
    t=strategy("uint256", max_value=10 * 86400),
)
@settings(**SETTINGS)
def test_price_scale_range(swap_with_deposit, coins, user, amount, i, j, t):
    if i == j:
        return

    prices1 = INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    with boa.env.prank(user):
        swap_with_deposit.exchange(i, j, amount, 0)

    prices2 = [swap_with_deposit.last_prices(k) for k in [0, 1]]
    boa.env.time_travel(seconds=t)

    with boa.env.prank(user):
        swap_with_deposit.remove_liquidity_one_coin(10**15, 0, 0)

    prices3 = [swap_with_deposit.price_scale(k) for k in [0, 1]]

    for p1, p2, p3 in zip(prices1[1:], prices2, prices3):
        if p1 > p2:
            assert p3 <= p1 and p3 >= p2
        else:
            assert p3 >= p1 and p3 <= p2


@given(
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_price_scale_change(swap_with_deposit, i, j, coins, user):

    if i == j:
        return

    amount = 10**6 * 10**18
    t = 86400

    prices1 = INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    out = coins[j].balanceOf(user)
    with boa.env.prank(user):
        swap_with_deposit.exchange(i, j, amount, 0)
    out = coins[j].balanceOf(user) - out

    price_scale_1 = [swap_with_deposit.price_scale(i) for i in range(2)]

    ix = j
    if i == 0:
        ix = j
    elif j == 0:
        ix = i

    boa.env.time_travel(seconds=t)
    mint_for_testing(coins[0], user, 10**18)

    with boa.env.prank(user):
        swap_with_deposit.exchange(0, 1, 10**18, 0)

    price_scale_2 = [swap_with_deposit.price_scale(i) for i in range(2)]
    price_diff = abs(price_scale_2[ix - 1] - price_scale_1[ix - 1])

    # checks if price scale changed is as expected:
    if price_diff > 0:

        rebal_params = swap_with_deposit.internal._unpack(
            swap_with_deposit._storage.packed_rebalancing_params.get()
        )

        price_oracle = [swap_with_deposit.price_oracle(k) for k in range(2)]

        _norm = norm(price_oracle, price_scale_1)
        step = max(rebal_params[1], _norm / 5)

        adjustment = int(
            step * abs(price_oracle[ix - 1] - price_scale_1[ix - 1]) / _norm
        )

        assert approx(adjustment, price_diff, 0.01)

    assert approx(
        swap_with_deposit._storage.virtual_price.get(),
        swap_with_deposit.get_virtual_price(),
        1e-10,
    )


def test_lp_price(swap_with_deposit):
    tvl = (
        swap_with_deposit.balances(0)
        + swap_with_deposit.balances(1)
        * swap_with_deposit.price_scale(0)
        // 10**18
        + swap_with_deposit.balances(2)
        * swap_with_deposit.price_scale(1)
        // 10**18
    )
    naive_price = tvl * 10**18 // swap_with_deposit.totalSupply()
    assert abs(swap_with_deposit.lp_price() / naive_price - 1) < 2e-3
