import boa
from hypothesis import settings  # noqa
from hypothesis import given
from hypothesis import strategies as st

from tests.utils import simulation_int_many as sim
from tests.utils.tokens import mint_for_testing

MAX_SAMPLES = 50


@boa.env.anchor()
def test_1st_deposit_and_last_withdraw(
    tricrypto_swap, coins, tricrypto_lp_token, user, initial_prices
):

    quantities = []
    for ix, c in enumerate(coins):
        quantities.append(10**6 // initial_prices[ix] * 10 ** c.decimals())

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
    values=st.lists(
        st.floats(min_value=0.01, max_value=10**9), min_size=3, max_size=3
    )
)
@settings(max_examples=MAX_SAMPLES, deadline=None)
@boa.env.anchor()
def test_second_deposit(
    tricrypto_swap_with_deposit,
    tricrypto_lp_token,
    coins,
    user,
    initial_prices,
    values,
):

    amounts = []
    for ix, c in enumerate(coins):
        amounts.append(
            int(values[ix] / initial_prices[ix] * 10 ** c.decimals())
        )

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
