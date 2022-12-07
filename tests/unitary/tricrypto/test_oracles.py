# TODO: update tests for upcoming get_p, _save_p, lp_price, etc.

from math import exp, log, log2, sqrt

import boa
from boa.test import strategy
from hypothesis import given, settings

from tests.conftest import INITIAL_PRICES
from tests.utils import mine
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision


def norm(swap):
    norm = 0
    for k in range(2):
        ratio = swap.price_oracle(k) * 10**18 / swap.price_scale(k)
        if ratio > 10**18:
            ratio -= 10**18
        else:
            ratio = 10**18 - ratio
        norm += ratio**2
    return sqrt(norm) / 10**18


def test_initial(tricrypto_swap_with_deposit):
    for i in range(2):
        assert tricrypto_swap_with_deposit.price_scale(i) == INITIAL_PRICES[i]
        assert tricrypto_swap_with_deposit.price_oracle(i) == INITIAL_PRICES[i]


# TODO: check if this test gets deprecated
@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_last_price_exchange(
    tricrypto_swap_with_deposit, coins, user, amount, i, j
):
    if i == j:
        return

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)

    out = coins[j].balanceOf(user)
    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.exchange(i, j, amount, 0)
    out = coins[j].balanceOf(user) - out

    if amount <= 10**5 or out <= 10**5:
        # A very rough sanity check
        for k in [1, 2]:
            oracle_price = tricrypto_swap_with_deposit.last_prices(k - 1)
            assert abs(log2(oracle_price / prices[k])) < 1
        return

    if i > 0 and j > 0:
        price_j = (
            tricrypto_swap_with_deposit.last_prices(i - 1) * amount // out
        )
        assert approx(
            price_j, tricrypto_swap_with_deposit.last_prices(j - 1), 2e-10
        )
    elif i == 0:
        price_j = amount * 10**18 // out
        assert approx(
            price_j, tricrypto_swap_with_deposit.last_prices(j - 1), 2e-10
        )
    else:  # j == 0
        price_i = out * 10**18 // amount
        assert approx(
            price_i, tricrypto_swap_with_deposit.last_prices(i - 1), 2e-10
        )


@given(
    token_frac=strategy("uint256", min_value=10**6, max_value=10**16),
    i=strategy("uint8", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_last_price_remove_liq(
    tricrypto_swap_with_deposit, tricrypto_lp_token, user, token_frac, i
):

    prices = [10**18] + INITIAL_PRICES
    token_amount = token_frac * tricrypto_lp_token.totalSupply() // 10**18

    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.remove_liquidity_one_coin(
            token_amount, i, 0
        )

    for k in [1, 2]:
        oracle_price = tricrypto_swap_with_deposit.last_prices(k - 1)
        assert abs(log2(oracle_price / prices[k])) < 0.1


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
    t=strategy("uint256", min_value=10, max_value=10 * 86400),
)
@settings(**SETTINGS)
def test_ma(tricrypto_swap_with_deposit, coins, user, amount, i, j, t):
    if i == j:
        return

    prices1 = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    exp_time = tricrypto_swap_with_deposit.ma_exp_time()

    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.exchange(i, j, amount, 0)

    prices2 = [tricrypto_swap_with_deposit.last_prices(k) for k in [0, 1]]

    boa.env.time_travel(t)

    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.remove_liquidity_one_coin(10**15, 0, 0)

    prices3 = [tricrypto_swap_with_deposit.price_oracle(k) for k in [0, 1]]

    for p1, p2, p3 in zip(INITIAL_PRICES, prices2, prices3):
        alpha = exp(-1 * t / exp_time)
        theory = p1 * alpha + p2 * (1 - alpha)
        assert abs(log2(theory / p3)) < 0.001


# Sanity check for price scale
@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
    t=strategy("uint256", max_value=10 * 86400),
)
@settings(**SETTINGS)
def test_price_scale_range(
    tricrypto_swap_with_deposit, coins, user, amount, i, j, t
):
    if i == j:
        return

    prices1 = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.exchange(i, j, amount, 0)

    prices2 = [tricrypto_swap_with_deposit.last_prices(k) for k in [0, 1]]
    boa.env.time_travel(seconds=t)

    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.remove_liquidity_one_coin(10**15, 0, 0)

    prices3 = [tricrypto_swap_with_deposit.price_scale(k) for k in [0, 1]]

    for p1, p2, p3 in zip(INITIAL_PRICES, prices2, prices3):
        if p1 > p2:
            assert p3 <= p1 and p3 >= p2
        else:
            assert p3 >= p1 and p3 <= p2


@given(
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_price_scale_change(tricrypto_swap_with_deposit, i, j, coins, user):
    amount = 10**5 * 10**18
    t = 86400

    if i == j:
        return

    prices1 = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices1[i]
    mint_for_testing(coins[i], user, amount)

    out = coins[j].balanceOf(user)
    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.exchange(i, j, amount, 0)
    out = coins[j].balanceOf(user) - out

    price_scale_1 = [
        tricrypto_swap_with_deposit.price_scale(i) for i in range(2)
    ]
    prices2 = [tricrypto_swap_with_deposit.last_prices(k) for k in [0, 1]]

    if i == 0:
        out_price = amount * 10**18 // out
        ix = j
    elif j == 0:
        out_price = out * 10**18 // amount
        ix = i
    else:
        ix = j
        out_price = amount * prices1[i] // out

    assert approx(out_price, prices2[ix - 1], 2e-10)
    boa.env.time_travel(seconds=t)

    mint_for_testing(coins[0], user, 10**18)
    with boa.env.prank(user), mine():
        tricrypto_swap_with_deposit.exchange(0, 1, 10**18, 0)

    price_scale_2 = [
        tricrypto_swap_with_deposit.price_scale(i) for i in range(2)
    ]

    price_diff = abs(log(price_scale_2[ix - 1] / price_scale_1[ix - 1]))
    step = max(
        tricrypto_swap_with_deposit.adjustment_step() / 10**18,
        norm(tricrypto_swap_with_deposit) / 10,
    )

    if not approx(price_diff, step, 0.15):
        assert False

    assert approx(
        tricrypto_swap_with_deposit.virtual_price(),
        tricrypto_swap_with_deposit.get_virtual_price(),
        1e-10,
    )
