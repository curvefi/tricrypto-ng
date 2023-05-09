from math import log

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 100, "deadline": None}


# flake8: noqa: E501
@pytest.fixture(scope="module")
def dydx_safemath():

    get_price_impl = """
N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(uint256) = 100

@external
@view
def get_p(
    _x1: uint256, _x2: uint256, _x3: uint256, _D: uint256, _A: uint256, _gamma: uint256,
) -> uint256:
    x1: int256 = convert(_x1, int256)
    x2: int256 = convert(_x2, int256)
    x3: int256 = convert(_x3, int256)
    D: int256 = convert(_D, int256)
    A: int256 = convert(_A, int256)
    gamma: int256 = convert(_gamma, int256)

    a: int256 = (
        (10**18 + gamma)*(-10**18 + gamma*(-2*10**18 + (-10**18 + 10**18*A/10000)*gamma/10**18)/10**18)/10**18 +
        81*(10**18 + gamma*(2*10**18 + gamma + 10**18*9*A/27/10000*gamma/10**18)/10**18)*x1/D*x2/D*x3/D -
        2187*(10**18 + gamma)*x1/D*x1/D*x2/D*x2/D*x3/D*x3/D +
        10**18*19683*x1/D*x1/D*x1/D*x2/D*x2/D*x2/D*x3/D*x3/D*x3/D
    )
    b: int256 = 10**18*729*A*x1/D*x2/D*x3/D*gamma**2/D/27/10000
    c: int256 = 27*A*gamma**2*(10**18 + gamma)/D/27/10000

    p: int256 = (
        10**18*x2*( 10**18*a - b*(x2 + x3)/10**18 - c*(2*x1 + x2 + x3)/10**18)
    )/(
        x1*(-10**18*a + b*(x1 + x3)/10**18 + c*(x1 + 2*x2 + x3)/10**18)
    )
    return convert(-p, uint256)
"""
    return boa.loads(get_price_impl)


# flake8: noqa: E501
@pytest.fixture(scope="module")
def dydx_optimised_math():

    get_price_impl = """
N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(uint256) = 100

@external
@view
def get_p(
    x1: uint256, x2: uint256, x3: uint256, D: uint256, ANN: uint256, gamma: uint256,
) -> uint256:

    S: uint256 = x1 + x2 + x3

    # we need K0, which is P * N**N / D**N:
    K: uint256 = 27 * x1 * x2 / D * x3 / D * 10**18 / D

    # G = 3 * K**2 - 2 * K * (2 * gamma + 3) + N_COINS**N_COINS * A * gamma**2 * (S - D) / D + (gamma + 1) * (gamma + 3)
    G: uint256 = (
          3 * K**2 / 10**18
        + 27 * ANN * gamma**2 * (S - D) / D / 27 / A_MULTIPLIER / 10**18
        + (gamma + 10**18) * (gamma + 3*10**18) / 10**18
        - 2 * K * (2 * gamma + 3*10**18) / 10**18
    )

    # G3 = G * D / (N_COINS**N_COINS * A * gamma**2)
    G3: uint256 = 27 * A_MULTIPLIER * G * D / gamma**2 / (27 * ANN)

    # p_y = (x / y) * ((G3 + y) / (G3 + x))
    # p_y: uint256 = x1 * (G3 * 10**18 + x2) * 10**18 / x2 / (G3 * 10**18 + x1)
    p_y: uint256 = x2 * (G3 * 10**18 + x1) * 10**18 / x1 / (G3 * 10**18 + x2)

    # print:
    # print("K           :", K)
    # print("G           :", G)
    # print("G3          :", G3)
    # print("p_y         :", p_y)

    return p_y
"""
    return boa.loads(get_price_impl, name="Optimised")


def _get_dydx_vyper(swap, i, j, price_calc):

    # ANN = swap.A()
    # A = ANN // 10**4 // 3**3
    A = swap.A()
    gamma = swap.gamma()

    xp = swap.internal.xp()

    for k in range(3):
        if k != i and k != j:
            break

    x1 = xp[i]
    x2 = xp[j]
    x3 = xp[k]

    D = swap.D()

    dxdy = price_calc.get_p(x1, x2, x3, D, A, gamma)
    print(f"dx/dy {price_calc.compiler_data.contract_name} =", dxdy)
    print("Gas used:", price_calc._computation.get_gas_used())
    return dxdy


def _get_prices_vyper(swap, price_calc):

    price_token_1_wrt_0 = _get_dydx_vyper(swap, 1, 0, price_calc)
    price_token_2_wrt_0 = _get_dydx_vyper(swap, 2, 0, price_calc)

    prices = [
        price_token_1_wrt_0 * swap.price_scale(0) // 10**18,
        price_token_2_wrt_0 * swap.price_scale(1) // 10**18,
    ]

    print(f"prices {price_calc.compiler_data.contract_name} =", prices, "\n")

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

    print("Prices Numeric:", prices, "\n")

    return prices


# ----- Tests -----


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
    dydx_safemath,
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

    dxdy_vyper = _get_prices_vyper(yuge_swap, dydx_safemath)
    dxdy_numeric_nofee = _get_prices_numeric_nofee(
        yuge_swap, views_contract, sell_usd=(i == 0)
    )
    dxdy_optimised_math_vyper = _get_prices_vyper(
        yuge_swap, dydx_optimised_math
    )

    for n in range(2):

        assert abs(log(dxdy_vyper[n] / dxdy_numeric_nofee[n])) < 1e-5
        assert (
            abs(log(dxdy_optimised_math_vyper[n] / dxdy_numeric_nofee[n]))
            < 1e-5
        )

        dxdy_swap = yuge_swap.last_prices(n)  # <-- we check unsafe impl here.
        assert abs(log(dxdy_vyper[n] / dxdy_swap)) < 1e-5


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dxdy_pump(yuge_swap, dydx_safemath, user, dollar_amount, coins, j):

    dxdy_math_0 = _get_prices_vyper(yuge_swap, dydx_safemath)
    dxdy_swap_0 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        yuge_swap.exchange(0, j, dx, 0)

    dxdy_math_1 = _get_prices_vyper(yuge_swap, dydx_safemath)
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
def test_dxdy_dump(yuge_swap, dydx_safemath, user, dollar_amount, coins, j):

    dxdy_math_0 = _get_prices_vyper(yuge_swap, dydx_safemath)
    dxdy_swap_0 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    dx = dollar_amount * 10**36 // INITIAL_PRICES[j]
    mint_for_testing(coins[j], user, dx)

    with boa.env.prank(user):
        yuge_swap.exchange(j, 0, dx, 0)

    dxdy_math_1 = _get_prices_vyper(yuge_swap, dydx_safemath)
    dxdy_swap_1 = [yuge_swap.last_prices(0), yuge_swap.last_prices(1)]

    for n in range(2):
        assert dxdy_math_1[n] < dxdy_math_0[n]
        assert dxdy_swap_1[n] < dxdy_swap_0[n]
