import boa
from boa.test import strategy
from hypothesis import given, settings  # noqa

from tests.conftest import INITIAL_PRICES
from tests.utils import simulation_int_many as sim
from tests.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 100, "deadline": None}


def test_1st_deposit_and_last_withdraw(
    tricrypto_swap, coins, tricrypto_lp_token, user
):

    quantities = [
        10**36 // p for p in [10**18] + INITIAL_PRICES
    ]  # $3 worth

    for coin, q in zip(coins, quantities):
        mint_for_testing(coin, user, q)
        with boa.env.prank(user):
            coin.approve(tricrypto_swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        tricrypto_swap.add_liquidity(quantities, 0)

    token_balance = tricrypto_lp_token.balanceOf(user)
    assert token_balance == tricrypto_lp_token.totalSupply() > 0
    assert abs(tricrypto_swap.get_virtual_price() / 1e18 - 1) < 1e-3

    # Empty the contract
    with boa.env.prank(user):
        tricrypto_swap.remove_liquidity(token_balance, [0] * 3)

    assert (
        tricrypto_lp_token.balanceOf(user)
        == tricrypto_lp_token.totalSupply()
        == 0
    )


@given(
    values=strategy(
        "uint256[3]", min_value=10**16, max_value=10**9 * 10**18
    )
)
@settings(**SETTINGS)
def test_second_deposit(
    tricrypto_swap_with_deposit,
    tricrypto_lp_token,
    coins,
    user,
    values,
):

    amounts = [
        v * 10**18 // p for v, p in zip(values, [10**18] + INITIAL_PRICES)
    ]

    # get simmed D value here:
    xp = [10**6 * 10**18] * 3  # initial D

    # D after second deposit:
    for i in range(3):
        xp[i] += int(values[i] * 10**18)

    _A = tricrypto_swap_with_deposit.A()
    _gamma = tricrypto_swap_with_deposit.gamma()
    _D = sim.solve_D(_A, _gamma, xp)

    safe = all(
        f >= 1.1e16 and f <= 0.9e20 for f in [_x * 10**18 // _D for _x in xp]
    )

    for c, v in zip(coins, amounts):
        mint_for_testing(c, user, v)

    try:

        calculated = tricrypto_swap_with_deposit.calc_token_amount(
            amounts, True
        )
        measured = tricrypto_lp_token.balanceOf(user)
        d_balances = [
            tricrypto_swap_with_deposit.balances(i) for i in range(3)
        ]

        with boa.env.prank(user):
            tricrypto_swap_with_deposit.add_liquidity(
                amounts, int(calculated * 0.999)
            )

        d_balances = [
            tricrypto_swap_with_deposit.balances(i) - d_balances[i]
            for i in range(3)
        ]
        measured = tricrypto_lp_token.balanceOf(user) - measured

        assert calculated == measured
        assert tuple(amounts) == tuple(d_balances)

    except Exception:

        if safe:
            raise

    # This is to check that we didn't end up in a borked state after
    # a deposit succeeded
    tricrypto_swap_with_deposit.get_dy(0, 1, 10**16)
    tricrypto_swap_with_deposit.get_dy(0, 2, 10**16)


@given(
    value=strategy(
        "uint256", min_value=10**16, max_value=10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_second_deposit_one(
    tricrypto_swap_with_deposit,
    tricrypto_lp_token,
    coins,
    user,
    value,
    i,
):

    amounts = [0] * 3
    amounts[i] = value * 10**18 // ([10**18] + INITIAL_PRICES)[i]
    mint_for_testing(coins[i], user, amounts[i])

    calculated = tricrypto_swap_with_deposit.calc_token_amount(amounts, True)
    measured = tricrypto_lp_token.balanceOf(user)
    d_balances = [tricrypto_swap_with_deposit.balances(i) for i in range(3)]

    with boa.env.prank(user):
        tricrypto_swap_with_deposit.add_liquidity(
            amounts, int(calculated * 0.999)
        )

    d_balances = [
        tricrypto_swap_with_deposit.balances(i) - d_balances[i]
        for i in range(3)
    ]
    measured = tricrypto_lp_token.balanceOf(user) - measured

    assert calculated == measured
    assert tuple(amounts) == tuple(d_balances)


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4000 * 10**18
    )
)  # supply is 2400 * 1e18
@settings(**SETTINGS)
def test_immediate_withdraw(
    tricrypto_swap_with_deposit, tricrypto_lp_token, coins, user, token_amount
):

    f = token_amount / tricrypto_lp_token.totalSupply()
    if f <= 1:
        expected = [
            int(f * tricrypto_swap_with_deposit.balances(i)) for i in range(3)
        ]
        measured = [c.balanceOf(user) for c in coins]
        token_amount_calc = tricrypto_swap_with_deposit.calc_token_amount(
            expected, False
        )
        assert abs(token_amount_calc - token_amount) / token_amount < 1e-3
        d_balances = [
            tricrypto_swap_with_deposit.balances(i) for i in range(3)
        ]

        with boa.env.prank(user):
            tricrypto_swap_with_deposit.remove_liquidity(
                token_amount,
                [int(0.999 * e) for e in expected],
            )

        d_balances = [
            d_balances[i] - tricrypto_swap_with_deposit.balances(i)
            for i in range(3)
        ]
        measured = [c.balanceOf(user) - m for c, m in zip(coins, measured)]

        for e, m in zip(expected, measured):
            assert abs(e - m) / e < 1e-3

        assert tuple(d_balances) == tuple(measured)

    else:
        with boa.reverts(), boa.env.prank(user):
            tricrypto_swap_with_deposit.remove_liquidity(token_amount, [0] * 3)


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_immediate_withdraw_one(
    tricrypto_swap_with_deposit,
    tricrypto_lp_token,
    coins,
    user,
    token_amount,
    i,
):

    if token_amount >= tricrypto_lp_token.totalSupply():
        with boa.reverts():
            tricrypto_swap_with_deposit.calc_withdraw_one_coin(token_amount, i)

    else:

        # Test if we are safe
        xp = [10**6 * 10**18] * 3
        _supply = tricrypto_lp_token.totalSupply()
        _A = tricrypto_swap_with_deposit.A()
        _gamma = tricrypto_swap_with_deposit.gamma()
        _D = (
            tricrypto_swap_with_deposit.D()
            * (_supply - token_amount)
            // _supply
        )
        xp[i] = sim.solve_x(_A, _gamma, xp, _D, i)
        safe = all(
            f >= 1.1e16 and f <= 0.9e20
            for f in [_x * 10**18 // _D for _x in xp]
        )

        try:
            calculated = tricrypto_swap_with_deposit.calc_withdraw_one_coin(
                token_amount, i
            )
        except Exception:
            if safe:
                raise
            return

        measured = coins[i].balanceOf(user)
        d_balances = [
            tricrypto_swap_with_deposit.balances(k) for k in range(3)
        ]
        try:
            with boa.env.prank(user):
                tricrypto_swap_with_deposit.remove_liquidity_one_coin(
                    token_amount, i, int(0.999 * calculated)
                )

        except Exception:

            # Check if it could fall into unsafe region here
            frac = (
                (d_balances[i] - calculated)
                * ([10**18] + INITIAL_PRICES)[i]
                // tricrypto_swap_with_deposit.D()
            )

            if frac > 1.1e16 or frac < 0.9e20:
                raise
            else:
                return

        d_balances = [
            d_balances[k] - tricrypto_swap_with_deposit.balances(k)
            for k in range(3)
        ]
        measured = coins[i].balanceOf(user) - measured

        assert calculated == measured

        for k in range(3):
            if k == i:
                assert d_balances[k] == measured
            else:
                assert d_balances[k] == 0

        # This is to check that we didn't end up in a borked state after
        # a withdrawal succeeded
        tricrypto_swap_with_deposit.get_dy(0, 1, 10**16)
        tricrypto_swap_with_deposit.get_dy(0, 2, 10**16)
