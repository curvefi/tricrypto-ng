from math import log

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 10000, "deadline": None}


# flake8: noqa: E501
@pytest.fixture(scope="module")
def get_price():

    get_price_impl = """
@external
@view
def get_price(
    _x1: uint256, _x2: uint256, _x3: uint256, _D: uint256, _gamma: uint256, _A: uint256
) -> uint256:

    x1: int256 = convert(_x1, int256)
    x2: int256 = convert(_x2, int256)
    x3: int256 = convert(_x3, int256)
    D: int256 = convert(_D, int256)
    gamma: int256 = convert(_gamma, int256)
    A: int256 = convert(_A, int256)

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

    return price_calc.get_price(x1, x2, x3, D, gamma, A)


def _get_prices_vyper(swap, price_calc):

    price_token_1_wrt_0 = _get_dydx_vyper(swap, 1, 0, price_calc)
    price_token_2_wrt_0 = _get_dydx_vyper(swap, 2, 0, price_calc)

    prices = [
        price_token_1_wrt_0 * swap.price_scale(0) // 10**18,
        price_token_2_wrt_0 * swap.price_scale(1) // 10**18,
    ]

    return prices


def _get_prices_numeric_nofee(swap, views):

    smol_dx = 10**18
    dy_nofee_token_1 = views.internal._get_dy_nofee(0, 1, smol_dx, swap)[0]
    dy_nofee_token_2 = views.internal._get_dy_nofee(0, 2, smol_dx, swap)[0]

    prices = [
        smol_dx * 10**18 // dy_nofee_token_1,
        smol_dx * 10**18 // dy_nofee_token_2,
    ]

    return prices


# ----- Tests -----


@given(
    dollar_amount=strategy(
        "uint256", min_value=5 * 10**4, max_value=5 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_similar(
    swap_with_deposit, get_price, views_contract, user, dollar_amount, coins, j
):

    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(0, j, dx, 0)

    dxdy_vyper = _get_prices_vyper(swap_with_deposit, get_price)
    dxdy_numeric_nofee = _get_prices_numeric_nofee(
        swap_with_deposit, views_contract
    )

    for n in range(2):
        assert abs(log(dxdy_vyper[n] / dxdy_numeric_nofee[n])) < 1e-5


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_pump(
    swap_with_deposit, get_price, user, dollar_amount, coins, j
):

    dydx_math_0 = _get_prices_vyper(swap_with_deposit, get_price)
    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(0, j, dx, 0)

    dydx_math_1 = _get_prices_vyper(swap_with_deposit, get_price)

    for n in range(2):
        assert dydx_math_1[n] > dydx_math_0[n]


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),
)
@settings(**SETTINGS)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_dump(
    swap_with_deposit, get_price, user, dollar_amount, coins, j
):

    dydx_math_0 = _get_prices_vyper(swap_with_deposit, get_price)

    dx = dollar_amount * 10**36 // INITIAL_PRICES[j]
    mint_for_testing(coins[j], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(j, 0, dx, 0)

    dydx_math_1 = _get_prices_vyper(swap_with_deposit, get_price)

    for n in range(2):
        assert dydx_math_1[n] < dydx_math_0[n]
