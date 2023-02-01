import boa
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing


def _get_price(x1, x2, x3, d, gamma, A):

    a = (
        d**9 * (1 + gamma) * (-1 + gamma * (-2 + (-1 + 27 * A) * gamma))
        + 81
        * d**6
        * (1 + gamma * (2 + gamma + 9 * A * gamma))
        * x1
        * x2
        * x3
        - 2187 * d**3 * (1 + gamma) * x1**2 * x2**2 * x3**2
        + 19683 * x1**3 * x2**3 * x3**3
    )
    b = 729 * A * d**5 * gamma**2 * x1 * x2 * x3
    c = 27 * A * d**8 * gamma**2 * (1 + gamma)

    return (x2 * (a - b * (x2 + x3) - c * (2 * x1 + x2 + x3))) / (
        x1 * (-a + b * (x1 + x3) + c * (x1 + 2 * x2 + x3))
    )


def _get_dydx_math(swap, i, j):

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


def _get_dydx(swap):

    return [
        abs(_get_dydx_math(swap, 0, 1) * swap.price_scale(0) / 1e18),
        abs(_get_dydx_math(swap, 0, 2) * swap.price_scale(1) / 1e18),
    ]


def _get_last_prices(swap):
    return [swap.last_prices(0) / 1e18, swap.last_prices(1) / 1e18]


@given(
    dollar_amount=strategy(
        "uint256", min_value=10**4, max_value=10**6
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(max_examples=10000, deadline=None)
def test_last_prices(
    swap_nofee_with_deposit, views_contract, user, dollar_amount, i, j, coins
):

    if i == j:
        return

    dx = dollar_amount * 10**36 // INITIAL_PRICES[i]
    mint_for_testing(coins[i], user, dx)

    with boa.env.prank(user):
        swap_nofee_with_deposit.exchange(i, j, dx, 0)

    dydx_math_1 = _get_dydx(swap_nofee_with_deposit)

    last_prices_1 = [
        dx // views_contract.get_dy(0, 1, dx, swap_nofee_with_deposit),
        dx // views_contract.get_dy(0, 2, dx, swap_nofee_with_deposit),
    ]

    for n in range(2):

        assert (
            abs(dydx_math_1[n] - last_prices_1[n]) < 3
        )  # 3 dolla difference (arbitrary)
