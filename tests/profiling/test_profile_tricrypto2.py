import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.conftest import INITIAL_PRICES
from tests.utils import simulation_int_many as sim
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 100, "deadline": None}


@given(
    value=strategy(
        "uint256", min_value=10**16, max_value=10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile
def test_deposit_swap2(
    swap2,
    coins,
    user,
    value,
    i,
):
    amounts = [0] * 3
    amounts[i] = value * 10**18 // ([10**18] + INITIAL_PRICES)[i]
    mint_for_testing(coins[i], user, amounts[i])
    with boa.env.prank(user):
        swap2.add_liquidity(amounts, 0)


@given(
    amount=strategy(
        "uint256", min_value=10**6, max_value=2 * 10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
    j=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile
def test_profile_exchange_swap2(
    swap2,
    coins,
    user,
    amount,
    i,
    j,
):

    if i == j:
        return

    prices = [10**18] + INITIAL_PRICES
    amount = amount * 10**18 // prices[i]
    mint_for_testing(coins[i], user, amount)
    calculated = swap2.get_dy(i, j, amount)

    with boa.env.prank(user):
        swap2.exchange(i, j, amount, int(0.999 * calculated))


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4000 * 10**18
    )
)
@settings(**SETTINGS)
@pytest.mark.profile
def test_withdraw_swap2(
    swap2,
    token2,
    user,
    token_amount,
):

    f = token_amount / token2.totalSupply()
    if not f <= 1:
        return

    expected = [int(f * swap2.balances(i)) for i in range(3)]
    with boa.env.prank(user):
        swap2.remove_liquidity(
            token_amount,
            [int(0.999 * e) for e in expected],
        )


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4 * 10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
@pytest.mark.profile
def test_withdraw_one_swap2(
    swap2,
    token2,
    coins,
    user,
    token_amount,
    i,
):

    if token_amount >= token2.totalSupply():
        with boa.reverts():
            swap2.calc_withdraw_one_coin(token_amount, i)

    else:

        # Test if we are safe
        xp = [10**6 * 10**18] * 3
        _supply = token2.totalSupply()
        _A = swap2.A()
        _gamma = swap2.gamma()
        _D = swap2.D() * (_supply - token_amount) // _supply
        xp[i] = sim.solve_x(_A, _gamma, xp, _D, i)
        safe = all(
            f >= 1.1e16 and f <= 0.9e20
            for f in [_x * 10**18 // _D for _x in xp]
        )

        try:
            calculated = swap2.calc_withdraw_one_coin(token_amount, i)
        except Exception:
            if safe:
                raise
            return

        measured = coins[i].balanceOf(user)
        d_balances = [swap2.balances(k) for k in range(3)]
        try:
            with boa.env.prank(user):
                swap2.remove_liquidity_one_coin(
                    token_amount, i, int(0.999 * calculated)
                )

        except Exception:

            # Check if it could fall into unsafe region here
            frac = (
                (d_balances[i] - calculated)
                * ([10**18] + INITIAL_PRICES)[i]
                // swap2.D()
            )

            if frac > 1.1e16 or frac < 0.9e20:
                raise
            else:
                return

        d_balances = [d_balances[k] - swap2.balances(k) for k in range(3)]
        measured = coins[i].balanceOf(user) - measured

        assert calculated == measured

        for k in range(3):
            if k == i:
                assert d_balances[k] == measured
            else:
                assert d_balances[k] == 0

        swap2.get_dy(0, 1, 10**16)
        swap2.get_dy(0, 2, 10**16)
