import boa
import pytest

from tests.boa.utils.tokens import mint_for_testing


@pytest.fixture(scope="module")
def user_b(users):
    return users[1]


@pytest.fixture(scope="module")
def custom_fee_receiver(users):
    return users[5]


def _generate_fee_activity(swap, coins, depositor, trader):
    amounts = [10**21, 10**20, 10**20]

    for idx, (coin, amount) in enumerate(zip(coins, amounts)):
        for account in (depositor, trader):
            mint_for_testing(coin, account, amount)
            with boa.env.prank(account):
                coin.approve(swap, 2**256 - 1)

    with boa.env.prank(depositor):
        swap.add_liquidity(amounts, 0)

    for coin in coins:
        with boa.env.prank(depositor):
            coin.approve(swap, 2**256 - 1)
        with boa.env.prank(trader):
            coin.approve(swap, 2**256 - 1)

    with boa.env.prank(trader):
        for _ in range(20):
            swap.exchange(0, 1, max(amounts[0] // 1000, 10**15), 0)
            swap.exchange(1, 0, max(amounts[1] // 1000, 10**14), 0)


def test_pool_fee_receiver_default_empty(swap):
    assert swap.pool_fee_receiver() == boa.eval("empty(address)")


def test_fee_receiver_returns_factory_default_when_pool_receiver_empty(
    swap, fee_receiver
):
    assert swap.pool_fee_receiver() == boa.eval("empty(address)")
    assert swap.fee_receiver() == fee_receiver


def test_set_pool_fee_receiver(factory_admin, swap, custom_fee_receiver):
    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(custom_fee_receiver)

    assert swap.pool_fee_receiver() == custom_fee_receiver


def test_fee_receiver_returns_pool_override(
    factory_admin, swap, fee_receiver, custom_fee_receiver
):
    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(custom_fee_receiver)

    assert swap.fee_receiver() == custom_fee_receiver
    assert swap.fee_receiver() != fee_receiver


def test_set_fee_receiver_reverts_for_non_admin(user, swap, custom_fee_receiver):
    with boa.reverts(dev="only owner"), boa.env.prank(user):
        swap.set_fee_receiver(custom_fee_receiver)


def test_reset_pool_fee_receiver_to_factory_default(
    factory_admin, swap, fee_receiver, custom_fee_receiver
):
    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(custom_fee_receiver)

    assert swap.fee_receiver() == custom_fee_receiver

    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(boa.eval("empty(address)"))

    assert swap.pool_fee_receiver() == boa.eval("empty(address)")
    assert swap.fee_receiver() == fee_receiver


def test_admin_fees_go_to_pool_fee_receiver(
    swap_with_deposit,
    coins,
    factory_admin,
    fee_receiver,
    custom_fee_receiver,
    user,
    user_b,
):
    swap = swap_with_deposit

    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(custom_fee_receiver)

    _generate_fee_activity(swap, coins, user, user_b)
    boa.env.time_travel(86401)

    factory_receiver_balances_before = [
        coin.balanceOf(fee_receiver) for coin in coins
    ]
    pool_receiver_balances_before = [
        coin.balanceOf(custom_fee_receiver) for coin in coins
    ]

    lp_balance = swap.balanceOf(user)
    withdraw_amount = max(lp_balance // 200, 10**16)

    with boa.env.prank(user):
        swap.remove_liquidity_one_coin(withdraw_amount, 0, 0)

    factory_receiver_balances_after = [
        coin.balanceOf(fee_receiver) for coin in coins
    ]
    pool_receiver_balances_after = [
        coin.balanceOf(custom_fee_receiver) for coin in coins
    ]

    # Factory receiver should not receive anything
    assert all(
        after == before
        for before, after in zip(
            factory_receiver_balances_before, factory_receiver_balances_after
        )
    )

    # Pool receiver should receive fees
    assert any(
        after > before
        for before, after in zip(
            pool_receiver_balances_before, pool_receiver_balances_after
        )
    )


def test_update_pool_fee_receiver_event(factory_admin, swap, custom_fee_receiver):
    with boa.env.prank(factory_admin):
        swap.set_fee_receiver(custom_fee_receiver)

    logs = swap.get_logs()
    assert len(logs) == 1
    assert logs[0].event_type.name == "UpdatePoolFeeReceiver"
    assert logs[0].args[0] == boa.eval("empty(address)")
    assert logs[0].args[1] == custom_fee_receiver
