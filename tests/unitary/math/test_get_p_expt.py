import math
from decimal import Decimal

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 1000, "deadline": None}


# flake8: noqa: E501
@pytest.fixture(scope="module")
def dydx_optimised_math():

    get_price_impl = """
N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(int256) = 10000

@external
@view
def get_p(
    _xp: uint256[N_COINS], _D: uint256, _A_gamma: uint256[N_COINS-1]
) -> int256[N_COINS-1]:

    D: int256 = convert(_D, int256)
    ANN: int256 = convert(_A_gamma[0], int256)
    gamma: int256 = convert(_A_gamma[1], int256)
    x: int256 = convert(_xp[0], int256)
    y: int256 = convert(_xp[1], int256)
    z: int256 = convert(_xp[2], int256)

    NN_A_gamma2: int256 = 27 * ANN * gamma**2
    S: int256 = x + y + z
    K: int256 = 27 * x * y / D * z / D * 10**36 / D
    G: int256 = (
        3 * K**2 / 10**36
        - K * (4 * gamma * 10**18 + 6 * 10**36) / 10**36
        + NN_A_gamma2 * (S - D) / D / 27 / A_MULTIPLIER
        + (gamma + 10**18) * (gamma +  3 * 10**18)
    )

    G3: int256 = G * D / NN_A_gamma2 * 10**18 * 27 * 10000 / 10**18
    return [
        x * (G3 + y) / y * 10**18 / (G3 + x),
        x * (G3 + z) / z * 10**18 / (G3 + x),
    ]
"""
    return boa.loads(get_price_impl, name="Optimised")


def get_p_decimal(X, D, ANN, gamma):

    X = [Decimal(_) for _ in X]
    P = 10**18 * X[0] * X[1] * X[2]
    N = len(X)
    D = Decimal(D)
    K0 = P / (Decimal(D) / N) ** N

    S = sum(X)

    x = X[0]
    y = X[1]
    z = X[2]

    G = (
        3 * K0**2
        - (2 * K0 * (2 * gamma + 3 * 10**18))
        + (N**N * ANN * gamma**2 * (S - D) / D / 27 / 10000)
        + (gamma + 10**18) * (gamma + 3 * 10**18)
    )
    G3 = G * D / (N**N * ANN * gamma**2) * 10**18 * 27 * 10000 / 10**18
    p = [
        x * (G3 + y) / y * 10**18 / (G3 + x),
        x * (G3 + z) / z * 10**18 / (G3 + x),
    ]
    return p


def approx(x1, x2, precision=1e-5):
    return abs(math.log(x1 / x2)) <= precision


def _check_p(a, b):

    assert a > 0
    assert b > 0

    if abs(a - b) <= 1:
        return True

    return approx(a, b, 1e-5)


def _get_prices_vyper(swap, price_calc):

    A = swap.A()
    gamma = swap.gamma()
    xp = swap.internal.xp()
    D = swap.D()

    try:
        p = price_calc.get_p(xp, D, [A, gamma])
    except:
        breakpoint()

    price_token_1_wrt_0 = p[0]
    price_token_2_wrt_0 = p[1]

    prices = [
        price_token_1_wrt_0 * swap.price_scale(0) // 10**18,
        price_token_2_wrt_0 * swap.price_scale(1) // 10**18,
    ]

    return prices


def _get_prices_numeric_nofee(swap, views, sell_usd):

    if sell_usd:

        dx = 10**16  # 0.01 USD
        dy = [
            views.internal._get_dy_nofee(0, 1, dx, swap)[0],
            views.internal._get_dy_nofee(0, 2, dx, swap)[0],
        ]
        prices = [dx * 10**18 // dy[0], dx * 10**18 // dy[1]]

    else:

        prices = []
        for i in range(1, 3):

            dx = int(0.01 * 10**36 // INITIAL_PRICES[i])
            dolla_out = views.internal._get_dy_nofee(i, 0, dx, swap)[0]
            prices.append(dolla_out * 10**18 // dx)

    return prices


# ----- Tests -----


def test_against_expt(dydx_optimised_math):

    ANN = 42253659
    gamma = 11720394944313222
    xp = [
        165898964704801767090,
        180089627760498533741,
        479703029155498241214,
    ]
    D = 798348646635793903194
    p = [950539494815349606, 589388920722357662]

    # test python implementation:
    output_python = get_p_decimal(xp, D, ANN, gamma)
    assert _check_p(output_python[0], p[0])
    assert _check_p(output_python[1], p[1])

    # test vyper implementation
    output_vyper = dydx_optimised_math.get_p(xp, D, [ANN, gamma])
    assert _check_p(output_vyper[0], p[0])
    assert _check_p(output_vyper[1], p[1])


@given(
    dollar_amount=strategy(
        "uint256", min_value=5 * 10**4, max_value=5 * 10**8
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("i", [0, 1, 2])
@pytest.mark.parametrize("j", [0, 1, 2])
def test_dxdy_similar(
    yuge_swap,
    dydx_optimised_math,
    views_contract,
    user,
    dollar_amount,
    coins,
    i,
    j,
):

    if i == j:
        return

    dx = dollar_amount * 10**36 // INITIAL_PRICES[i]
    mint_for_testing(coins[i], user, dx)

    with boa.env.prank(user):
        yuge_swap.exchange(i, j, dx, 0)

    dxdy_vyper = _get_prices_vyper(yuge_swap, dydx_optimised_math)
    dxdy_numeric_nofee = _get_prices_numeric_nofee(
        yuge_swap, views_contract, sell_usd=(i == 0)
    )

    for n in range(2):

        assert abs(math.log(dxdy_vyper[n] / dxdy_numeric_nofee[n])) < 1e-5
        assert approx(dxdy_vyper[n], dxdy_numeric_nofee[n])

        dxdy_swap = yuge_swap.last_prices(n)  # <-- we check unsafe impl here.
        assert abs(math.log(dxdy_vyper[n] / dxdy_swap)) < 1e-5


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dxdy_pump(
    yuge_swap, dydx_optimised_math, user, dollar_amount, coins, j
):

    dxdy_math_0 = _get_prices_vyper(yuge_swap, dydx_optimised_math)
    dxdy_swap_0 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        yuge_swap.exchange(0, j, dx, 0)

    dxdy_math_1 = _get_prices_vyper(yuge_swap, dydx_optimised_math)
    dxdy_swap_1 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    for n in range(2):
        assert dxdy_math_1[n] > dxdy_math_0[n]
        assert dxdy_swap_1[n] > dxdy_swap_0[n]


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dxdy_dump(
    yuge_swap, dydx_optimised_math, user, dollar_amount, coins, j
):

    dxdy_math_0 = _get_prices_vyper(yuge_swap, dydx_optimised_math)
    dxdy_swap_0 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    dx = dollar_amount * 10**36 // INITIAL_PRICES[j]
    mint_for_testing(coins[j], user, dx)

    with boa.env.prank(user):
        yuge_swap.exchange(j, 0, dx, 0)

    dxdy_math_1 = _get_prices_vyper(yuge_swap, dydx_optimised_math)
    dxdy_swap_1 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    for n in range(2):
        assert dxdy_math_1[n] < dxdy_math_0[n]
        assert dxdy_swap_1[n] < dxdy_swap_0[n]
