import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing


def _get_price(x1, x2, x3, D, gamma, A):

    a = (
        D**9 * (1 + gamma) * (-1 + gamma * (-2 + (-1 + 27 * A) * gamma))
        + 81
        * D**6
        * (1 + gamma * (2 + gamma + 9 * A * gamma))
        * x1
        * x2
        * x3
        - 2187 * D**3 * (1 + gamma) * x1**2 * x2**2 * x3**2
        + 19683 * x1**3 * x2**3 * x3**3
    )
    b = 729 * A * D**5 * gamma**2 * x1 * x2 * x3
    c = 27 * A * D**8 * gamma**2 * (1 + gamma)

    return (x2 * (a - b * (x2 + x3) - c * (2 * x1 + x2 + x3))) / (
        x1 * (-a + b * (x1 + x3) + c * (x1 + 2 * x2 + x3))
    )


def _get_dydx(swap, i, j):

    ANN = swap.A()
    A = ANN / 10**4 / 3**3
    gamma = swap.gamma() / 10**18

    xp = swap.internal.xp()

    for k in range(3):
        if k != i and k != j:
            break

    x1 = xp[i] / 1e18
    x2 = xp[j] / 1e18
    x3 = xp[k] / 1e18

    D = swap.D() / 1e18

    return _get_price(x1, x2, x3, D, gamma, A)


def _get_prices_math(swap):

    # invert to get dx/dy, else it returns dy/dx
    return [
        abs(1 / _get_dydx(swap, 0, 1) * swap.price_scale(0) / 1e18),
        abs(1 / _get_dydx(swap, 0, 2) * swap.price_scale(1) / 1e18),
    ]


def _get_prices_numeric_nofee(swap, views):

    smol_dx = 10**18
    return [
        smol_dx / views.internal._get_dy_nofee(0, 1, smol_dx, swap)[0],
        smol_dx / views.internal._get_dy_nofee(0, 2, smol_dx, swap)[0],
    ]


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),  # Can be more than we have
)
@settings(max_examples=100, deadline=None)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_pump(swap_with_deposit, user, dollar_amount, coins, j):

    dydx_math_0 = _get_prices_math(swap_with_deposit)
    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(0, j, dx, 0)

    dydx_math_1 = _get_prices_math(swap_with_deposit)

    for n in range(2):
        assert dydx_math_1[n] > dydx_math_0[n]


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=4 * 10**5
    ),  # Can be more than we have
)
@settings(max_examples=100, deadline=None)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_dump(swap_with_deposit, user, dollar_amount, coins, j):

    dydx_math_0 = _get_prices_math(swap_with_deposit)

    dx = dollar_amount * 10**36 // INITIAL_PRICES[j]
    mint_for_testing(coins[j], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(j, 0, dx, 0)

    dydx_math_1 = _get_prices_math(swap_with_deposit)

    for n in range(2):
        assert dydx_math_1[n] < dydx_math_0[n]


@given(
    dollar_amount=strategy(
        "uint256", min_value=5 * 10**4, max_value=5 * 10**5
    ),  # Can be more than we have
)
@settings(max_examples=100, deadline=None)
@pytest.mark.parametrize("j", [1, 2])
def test_dydx_similar(
    swap_with_deposit, views_contract, user, dollar_amount, coins, j
):

    dx = dollar_amount * 10**18
    mint_for_testing(coins[0], user, dx)

    with boa.env.prank(user):
        swap_with_deposit.exchange(0, j, dx, 0)

    dydx_math = _get_prices_math(swap_with_deposit)
    dydx_numeric_nofee = _get_prices_numeric_nofee(
        swap_with_deposit, views_contract
    )

    for n in range(2):
        diff = dydx_math[n] - dydx_numeric_nofee[n]
        assert abs(diff) < 1
