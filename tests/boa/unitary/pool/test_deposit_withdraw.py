import math

import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.boa.fixtures.pool import INITIAL_PRICES
from tests.boa.utils import simulation_int_many as sim
from tests.boa.utils.tokens import mint_for_testing

SETTINGS = {"max_examples": 100, "deadline": None}


def approx(x1, x2, precision):
    return abs(math.log(x1 / x2)) <= precision


def assert_string_contains(string, substrings):
    assert any(substring in string for substring in substrings)


@pytest.fixture(scope="module")
def test_1st_deposit_and_last_withdraw(swap, coins, user, fee_receiver):

    quantities = [10**36 // p for p in INITIAL_PRICES]  # $3M worth

    for coin, q in zip(coins, quantities):
        mint_for_testing(coin, user, q)
        with boa.env.prank(user):
            coin.approve(swap, 2**256 - 1)

    bal_before = boa.env.get_balance(swap.address)
    with boa.env.prank(user):
        swap.add_liquidity(quantities, 0)

    # test if eth wasnt deposited:
    assert boa.env.get_balance(swap.address) == bal_before

    token_balance = swap.balanceOf(user)
    assert (
        token_balance == swap.totalSupply() - swap.balanceOf(fee_receiver) > 0
    )
    assert abs(swap.get_virtual_price() / 1e18 - 1) < 1e-3

    # Empty the contract
    with boa.env.prank(user):
        swap.remove_liquidity(token_balance, [0] * 3)

    # nothing is left except admin balances
    assert (
        swap.balanceOf(user)
        == swap.totalSupply() - swap.balanceOf(fee_receiver)
        == 0
    )

    return swap


@pytest.fixture(scope="module")
def test_first_deposit_full_withdraw_second_deposit(
    test_1st_deposit_and_last_withdraw, user, coins, fee_receiver
):
    swap = test_1st_deposit_and_last_withdraw
    quantities = [10**36 // p for p in INITIAL_PRICES]  # $3M worth

    for coin, q in zip(coins, quantities):
        mint_for_testing(coin, user, q)
        with boa.env.prank(user):
            coin.approve(swap, 2**256 - 1)

    # Second deposit
    eth_bal_before = boa.env.get_balance(swap.address)
    swap_balances_before = [swap.balances(i) for i in range(3)]
    with boa.env.prank(user):
        swap.add_liquidity(quantities, 0)

    assert swap.xcp_profit_a() >= 10**18
    assert swap.xcp_profit() >= 10**18
    assert swap.virtual_price() >= 10**18

    # test if eth was not deposited:
    assert boa.env.get_balance(swap.address) == eth_bal_before

    for i in range(len(coins)):
        assert swap.balances(i) == quantities[i] + swap_balances_before[i]

    token_balance = swap.balanceOf(user)
    assert (
        token_balance + swap.balanceOf(fee_receiver) == swap.totalSupply() > 0
    )
    assert abs(swap.get_virtual_price() / 1e18 - 1) < 1e-3

    return swap


@given(
    i=strategy("uint", min_value=0, max_value=2),
    amount=strategy("uint256", max_value=2000, min_value=1),
)
@settings(**SETTINGS)
def test_second_deposit_single_token(
    swap_with_deposit, coins, user, i, amount
):

    # deposit single token:
    quantities = [0, 0, 0]
    for j in range(3):
        if j == i:
            quantities[j] = amount * 10 ** coins[i].decimals()
            mint_for_testing(coins[j], user, quantities[j])

    # Single sided deposit
    with boa.env.prank(user):
        swap_with_deposit.add_liquidity(quantities, 0)


@given(
    values=strategy(
        "uint256[3]", min_value=10**16, max_value=10**9 * 10**18
    )
)
@settings(**SETTINGS)
def test_second_deposit(
    swap_with_deposit,
    coins,
    user,
    values,
):

    amounts = [v * 10**18 // p for v, p in zip(values, INITIAL_PRICES)]

    # get simmed D value here:
    xp = [10**6 * 10**18] * 3  # initial D

    # D after second deposit:
    for i in range(3):
        xp[i] += int(values[i] * 10**18)

    _A, _gamma = [swap_with_deposit.A(), swap_with_deposit.gamma()]
    _D = sim.solve_D(_A, _gamma, xp)

    safe = all(
        f >= 1.1e16 and f <= 0.9e20 for f in [_x * 10**18 // _D for _x in xp]
    )

    for coin, q in zip(coins, amounts):
        mint_for_testing(coin, user, 10**30)
        with boa.env.prank(user):
            coin.approve(swap_with_deposit, 2**256 - 1)

    try:

        calculated = swap_with_deposit.calc_token_amount(amounts, True)
        measured = swap_with_deposit.balanceOf(user)
        d_balances = [swap_with_deposit.balances(i) for i in range(3)]
        claimed_fees = [0, 0, 0]

        with boa.env.prank(user):
            swap_with_deposit.add_liquidity(amounts, int(calculated * 0.999))

        logs = swap_with_deposit.get_logs()
        for log in logs:
            if log.event_type.name == "ClaimAdminFee":
                claimed_fees = log.args[0]

        d_balances = [
            swap_with_deposit.balances(i) - d_balances[i] + claimed_fees[i]
            for i in range(3)
        ]
        measured = swap_with_deposit.balanceOf(user) - measured

        assert calculated <= measured
        assert tuple(amounts) == tuple(d_balances)

    except Exception:

        if safe:
            raise

    # This is to check that we didn't end up in a borked state after
    # a deposit succeeded
    swap_with_deposit.get_dy(0, 1, 10**16)
    swap_with_deposit.get_dy(0, 2, 10**16)


@given(
    value=strategy(
        "uint256", min_value=10**16, max_value=10**6 * 10**18
    ),
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_second_deposit_one(
    swap_with_deposit,
    views_contract,
    coins,
    user,
    value,
    i,
):

    amounts = [0] * 3
    amounts[i] = value * 10**18 // (INITIAL_PRICES)[i]
    mint_for_testing(coins[i], user, amounts[i])

    try:

        calculated = views_contract.calc_token_amount(
            amounts, True, swap_with_deposit
        )
        measured = swap_with_deposit.balanceOf(user)
        d_balances = [swap_with_deposit.balances(i) for i in range(3)]
        claimed_fees = [0, 0, 0]

        with boa.env.prank(user):
            swap_with_deposit.add_liquidity(amounts, int(calculated * 0.999))

        logs = swap_with_deposit.get_logs()
        for log in logs:
            if log.event_type.name == "ClaimAdminFee":
                claimed_fees = log.args[0]

        d_balances = [
            swap_with_deposit.balances(i) - d_balances[i] + claimed_fees[i]
            for i in range(3)
        ]
        measured = swap_with_deposit.balanceOf(user) - measured

        assert calculated <= measured
        assert tuple(amounts) == tuple(d_balances)

    except boa.BoaError as b_error:

        assert_string_contains(
            b_error.stack_trace.last_frame.pretty_vm_reason,
            ["Unsafe value for y", "Unsafe values x[i]"],
        )


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4000 * 10**18
    )
)  # supply is 2400 * 1e18
@settings(**SETTINGS)
def test_immediate_withdraw(
    swap_with_deposit,
    views_contract,
    coins,
    user,
    token_amount,
):

    f = token_amount / swap_with_deposit.totalSupply()
    if f <= 1:
        expected = [int(f * swap_with_deposit.balances(i)) for i in range(3)]
        measured = [c.balanceOf(user) for c in coins]
        token_amount_calc = views_contract.calc_token_amount(
            expected, False, swap_with_deposit
        )
        assert abs(token_amount_calc - token_amount) / token_amount < 1e-3
        d_balances = [swap_with_deposit.balances(i) for i in range(3)]

        with boa.env.prank(user):
            swap_with_deposit.remove_liquidity(
                token_amount,
                [int(0.999 * e) for e in expected],
            )

        d_balances = [
            d_balances[i] - swap_with_deposit.balances(i) for i in range(3)
        ]
        measured = [c.balanceOf(user) - m for c, m in zip(coins, measured)]

        for e, m in zip(expected, measured):
            assert abs(e - m) / e < 1e-3

        assert tuple(d_balances) == tuple(measured)

    else:
        with boa.reverts(), boa.env.prank(user):
            swap_with_deposit.remove_liquidity(token_amount, [0] * 3)


@given(
    token_amount=strategy(
        "uint256", min_value=10**12, max_value=4 * 10**6 * 10**18
    ),  # Can be more than we have
    i=strategy("uint", min_value=0, max_value=2),
)
@settings(**SETTINGS)
def test_immediate_withdraw_one(
    swap_with_deposit,
    views_contract,
    coins,
    user,
    token_amount,
    i,
):

    if token_amount >= swap_with_deposit.totalSupply():
        with boa.reverts():
            swap_with_deposit.calc_withdraw_one_coin(token_amount, i)

    else:

        # Test if we are safe
        xp = [10**6 * 10**18] * 3
        _supply = swap_with_deposit.totalSupply()
        _A, _gamma = [swap_with_deposit.A(), swap_with_deposit.gamma()]
        _D = swap_with_deposit.D() * (_supply - token_amount) // _supply

        xp[i] = sim.solve_x(_A, _gamma, xp, _D, i)

        safe = all(
            f >= 1.1e16 and f <= 0.9e20
            for f in [_x * 10**18 // _D for _x in xp]
        )

        try:
            calculated = swap_with_deposit.calc_withdraw_one_coin(
                token_amount, i
            )
        except Exception:
            if safe:
                raise
            return

        measured = coins[i].balanceOf(user)
        d_balances = [swap_with_deposit.balances(k) for k in range(3)]
        claimed_fees = [0, 0, 0]
        try:
            with boa.env.prank(user):
                swap_with_deposit.remove_liquidity_one_coin(
                    token_amount, i, int(0.999 * calculated)
                )

            logs = swap_with_deposit.get_logs()
            for log in logs:
                if log.event_type.name == "ClaimAdminFee":
                    claimed_fees = log.args[0]

        except Exception:

            # Check if it could fall into unsafe region here
            frac = (
                (d_balances[i] - calculated)
                * (INITIAL_PRICES)[i]
                // swap_with_deposit.D()
            )

            if frac > 1.1e16 and frac < 0.9e20:
                raise
            return  # dont continue tests

        d_balances = [
            d_balances[k] - swap_with_deposit.balances(k) for k in range(3)
        ]
        measured = coins[i].balanceOf(user) - measured

        assert calculated >= measured
        assert calculated - (0.01 / 100) * calculated < measured
        assert approx(calculated, measured, 1e-3)

        for k in range(3):
            claimed_tokens = claimed_fees[k]
            if k == i:
                assert d_balances[k] == measured + claimed_tokens
            else:
                assert d_balances[k] == claimed_tokens

        # This is to check that we didn't end up in a borked state after
        # a withdrawal succeeded
        views_contract.get_dy(0, 1, 10**16, swap_with_deposit)
        views_contract.get_dy(0, 2, 10**16, swap_with_deposit)
