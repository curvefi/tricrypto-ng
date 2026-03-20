import boa
import pytest

from tests.boa.utils.tokens import mint_for_testing

NEW_ADMIN_FEE = 3 * 10**9
DEFAULT_ADMIN_FEE = 5 * 10**9
MAX_ADMIN_FEE = 10**10


@pytest.fixture(scope="module")
def admin_fee_default():
    return DEFAULT_ADMIN_FEE


@pytest.fixture(scope="module")
def user_b(users):
    return users[1]


def _generate_fee_activity(swap, coins, depositor, trader):
    # small amount still generates admin fees without tripping math safety checks
    amounts = [10**21, 10**20, 10**20]

    for idx, (coin, amount) in enumerate(zip(coins, amounts)):
        for account in (depositor, trader):
            mint_for_testing(coin, account, amount)
            with boa.env.prank(account):
                coin.approve(swap, 2**256 - 1)

    with boa.env.prank(depositor):
        swap.add_liquidity(amounts, 0)

    # top up approvals for remaining trader operations
    for coin in coins:
        with boa.env.prank(depositor):
            coin.approve(swap, 2**256 - 1)
        with boa.env.prank(trader):
            coin.approve(swap, 2**256 - 1)

    with boa.env.prank(trader):
        for _ in range(20):
            swap.exchange(0, 1, max(amounts[0] // 1000, 10**15), 0)
            swap.exchange(1, 0, max(amounts[1] // 1000, 10**14), 0)


def test_admin_fee_default(swap, admin_fee_default):
    assert swap.admin_fee() == admin_fee_default


def test_admin_fee_update(factory_admin, swap):
    with boa.env.prank(factory_admin):
        swap.set_admin_fee(NEW_ADMIN_FEE)

    assert swap.admin_fee() == NEW_ADMIN_FEE


def test_admin_fee_reverts_for_non_admin(user, swap):
    with boa.reverts(dev="only owner"), boa.env.prank(user):
        swap.set_admin_fee(NEW_ADMIN_FEE)


def test_admin_fee_reverts_above_cap(factory_admin, swap):
    with boa.env.prank(factory_admin):
        with boa.reverts(dev="above cap"):
            swap.set_admin_fee(MAX_ADMIN_FEE + 1)


def test_admin_fee_claims_with_new_rate(
    swap_with_deposit,
    coins,
    factory_admin,
    fee_receiver,
    user,
    user_b,
):
    swap = swap_with_deposit

    _generate_fee_activity(swap, coins, user, user_b)
    boa.env.time_travel(86401)

    balances_before = [coin.balanceOf(fee_receiver) for coin in coins]

    with boa.env.prank(factory_admin):
        swap.set_admin_fee(NEW_ADMIN_FEE)

    lp_balance = swap.balanceOf(user)
    withdraw_amount = max(lp_balance // 200, 10**16)

    with boa.env.prank(user):
        swap.remove_liquidity_one_coin(withdraw_amount, 0, 0)

    balances_after = [coin.balanceOf(fee_receiver) for coin in coins]

    assert swap.admin_fee() == NEW_ADMIN_FEE
    assert any(
        after > before for before, after in zip(balances_before, balances_after)
    )
