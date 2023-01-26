import boa
import pytest
from boa.test import strategy
from hypothesis import given, settings

from tests.utils.tokens import mint_for_testing


@pytest.fixture(scope="module")
def callbacker():
    return boa.env.generate_address()


@pytest.fixture(scope="module", autouse=True)
def zap(swap_with_deposit, coins, callbacker):

    with boa.env.prank(callbacker):
        _zap = boa.load(
            "contracts/mocks/CallbackTestZap.vy", swap_with_deposit.address
        )
        for coin in coins:
            coin.approve(_zap.address, 2**256 - 1)

    return _zap


@given(
    dx=strategy("uint256", min_value=1000 * 10**6, max_value=100 * 10**18),
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(deadline=None)
def test_revert_good_callback_not_enough_coins(zap, callbacker, i, j, dx):
    if i == j:
        return

    with boa.env.prank(callbacker), boa.reverts():
        zap.good_exchange(i, j, dx, 0)


@given(
    dx=strategy("uint256", min_value=1000 * 10**6, max_value=100 * 10**18),
    j=strategy("uint8", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_revert_good_callback_input_eth(zap, callbacker, coins, j, dx):

    mint_for_testing(coins[2], callbacker, dx, True)

    with boa.env.prank(callbacker), boa.reverts():
        zap.good_exchange(2, j, dx, 0, True, value=dx)


@given(
    dx=strategy("uint256", min_value=1000 * 10**6, max_value=100 * 10**18),
    i=strategy("uint8", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_success_good_callback_output_eth(
    swap_with_deposit, views_contract, zap, callbacker, coins, i, dx
):

    mint_for_testing(coins[i], callbacker, dx)

    dy = views_contract.get_dy(i, 2, dx, swap_with_deposit)

    bal_before = boa.env.get_balance(callbacker)
    bal_weth_before = coins[2].balanceOf(callbacker)
    bal_in_before = coins[i].balanceOf(callbacker)

    with boa.env.prank(callbacker):
        out = zap.good_exchange(i, 2, dx, 0, True)

    assert out == dy
    assert boa.env.get_balance(callbacker) == bal_before + dy
    assert coins[2].balanceOf(callbacker) == bal_weth_before
    assert coins[i].balanceOf(callbacker) == bal_in_before - dx


@given(
    dx=strategy("uint256", min_value=1000 * 10**6, max_value=100 * 10**18),
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(deadline=None)
def test_good_callback_erc20(
    swap_with_deposit, views_contract, zap, callbacker, coins, i, j, dx
):
    if i == j:
        return

    dy = views_contract.get_dy(i, j, dx, swap_with_deposit)

    mint_for_testing(coins[i], callbacker, dx, False)

    with boa.env.prank(callbacker):
        zap.good_exchange(i, j, dx, 0, False)

    assert zap.input_amount() == dx
    assert zap.output_amount() == dy


@given(
    dx=strategy("uint256", min_value=1000 * 10**6, max_value=100 * 10**18),
    i=strategy("uint8", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_good_callback_output_eth(
    swap_with_deposit, views_contract, zap, callbacker, coins, i, dx
):

    dy = views_contract.get_dy(i, 2, dx, swap_with_deposit)

    mint_for_testing(coins[i], callbacker, dx)

    with boa.env.prank(callbacker):
        zap.good_exchange(i, 2, dx, 0, True)

    assert zap.input_amount() == dx
    assert zap.output_amount() == dy


@given(
    amount=strategy(
        "uint256", min_value=1000 * 10**6, max_value=100 * 10**18
    ),
    i=strategy("uint8", min_value=0, max_value=2),
    j=strategy("uint8", min_value=0, max_value=2),
)
@settings(deadline=None)
def test_evil_callback_erc20(zap, coins, i, j, callbacker, amount):

    if i == j:
        return

    mint_for_testing(coins[i], callbacker, amount * 2, False)

    # set dx in callback sig to half of amount:
    # callback sends 2x what it exchanges.
    with boa.env.prank(callbacker):
        zap.set_evil_input_amount(amount * 2)

        with boa.reverts():
            zap.evil_exchange(i, j, amount, 0, False)

    # set dx in callback sig to twice the amount:
    # callback sends pool half of what it exchanges.
    with boa.env.prank(callbacker):
        zap.set_evil_input_amount(amount // 2)

        with boa.reverts():
            zap.evil_exchange(i, j, amount, 0, False)
