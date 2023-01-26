import boa
from boa.test import strategy
from hypothesis import given, settings

from tests.fixtures.pool import INITIAL_PRICES, _get_deposit_amounts
from tests.utils.tokens import mint_for_testing


@given(
    amount=strategy("uint256", min_value=10**7, max_value=10**18),
    i=strategy("uint256", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_exchange_eth_in(swap_with_deposit, amount, coins, user, i):

    assert coins[i].balanceOf(user) == 0
    swap_eth_balance = boa.env.get_balance(swap_with_deposit.address)
    swap_token_balance = swap_with_deposit.balances(i)

    with boa.env.prank(user):
        dy = swap_with_deposit.exchange(2, i, amount, 0, True, value=amount)

    assert coins[i].balanceOf(user) > 0
    assert (
        boa.env.get_balance(swap_with_deposit.address)
        == amount + swap_eth_balance
    )
    assert swap_with_deposit.balances(i) == swap_token_balance - dy


@given(
    amount=strategy("uint256", min_value=10**7, max_value=10**18),
    i=strategy("uint256", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_exchange_underlying_eth_in(swap_with_deposit, amount, coins, user, i):

    assert coins[i].balanceOf(user) == 0
    swap_eth_balance = boa.env.get_balance(swap_with_deposit.address)
    swap_token_balance = swap_with_deposit.balances(i)

    with boa.env.prank(user):
        dy = swap_with_deposit.exchange_underlying(
            2, i, amount, 0, value=amount
        )

    assert coins[i].balanceOf(user) > 0
    assert (
        boa.env.get_balance(swap_with_deposit.address)
        == amount + swap_eth_balance
    )
    assert swap_with_deposit.balances(i) == swap_token_balance - dy


@given(
    amount=strategy("uint256", min_value=10**7, max_value=10**18),
    i=strategy("uint256", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_exchange_eth_out(swap_with_deposit, amount, coins, user, i):

    old_balance = boa.env.get_balance(user)
    swap_eth_balance = boa.env.get_balance(swap_with_deposit.address)
    swap_token_balance = swap_with_deposit.balances(i)

    mint_for_testing(coins[i], user, amount)

    with boa.env.prank(user):
        swap_with_deposit.exchange(i, 2, amount, 0, True)

    assert boa.env.get_balance(user) - old_balance > 0
    assert boa.env.get_balance(
        user
    ) - old_balance == swap_eth_balance - swap_with_deposit.balances(2)
    assert swap_with_deposit.balances(i) - swap_token_balance == amount


@given(
    amount=strategy("uint256", min_value=10**7, max_value=10**18),
    i=strategy("uint256", min_value=0, max_value=1),
)
@settings(deadline=None)
def test_exchange_underlying_eth_out(
    swap_with_deposit, amount, coins, user, i
):

    old_balance = boa.env.get_balance(user)
    swap_eth_balance = boa.env.get_balance(swap_with_deposit.address)
    swap_token_balance = swap_with_deposit.balances(i)

    mint_for_testing(coins[i], user, amount)

    with boa.env.prank(user):
        swap_with_deposit.exchange_underlying(i, 2, amount, 0)

    assert boa.env.get_balance(user) - old_balance > 0
    assert boa.env.get_balance(
        user
    ) - old_balance == swap_eth_balance - swap_with_deposit.balances(2)
    assert swap_with_deposit.balances(i) - swap_token_balance == amount


@given(
    amount_usd=strategy("uint256", min_value=1, max_value=10**8),
    use_eth=strategy("bool"),
)
@settings(deadline=None)
def test_add_liquidity_eth(swap, coins, user, amount_usd, use_eth):

    amounts = _get_deposit_amounts(amount_usd, INITIAL_PRICES, coins)

    for i in range(3):
        if i == 2 and use_eth:
            mint_for_testing(coins[i], user, amounts[i], True)
        else:
            mint_for_testing(coins[i], user, amounts[i])

    initial_coin_balances = [c.balanceOf(user) for c in coins]
    initial_eth_balance = boa.env.get_balance(user)

    with boa.env.prank(user):
        for coin in coins:
            coin.approve(swap, 2**256 - 1)

    if use_eth:
        with boa.env.prank(user):
            with boa.reverts(dev="incorrect eth amount"):
                swap.add_liquidity(amounts, 0, True)

            swap.add_liquidity(amounts, 0, True, value=amounts[2])

        assert coins[2].balanceOf(user) == initial_coin_balances[2]
        assert initial_eth_balance - boa.env.get_balance(user) == amounts[2]

    else:
        with boa.env.prank(user):
            with boa.reverts(dev="nonzero eth amount"):
                swap.add_liquidity(amounts, 0, False, value=amounts[2])

            swap.add_liquidity(amounts, 0, False)

        assert (
            initial_coin_balances[2] - coins[2].balanceOf(user) == amounts[2]
        )
        assert initial_eth_balance == boa.env.get_balance(user)

    for i in range(3):
        if i == 2:
            break
        assert (
            initial_coin_balances[i] - coins[i].balanceOf(user) == amounts[i]
        )


@given(
    frac=strategy("uint256", min_value=10**10, max_value=10**18),
    use_eth=strategy("bool"),
)
def test_remove_liquidity_eth(swap_with_deposit, coins, user, frac, use_eth):

    token_amount = swap_with_deposit.balanceOf(user) * frac // 10**18
    assert token_amount > 0

    initial_coin_balances = [c.balanceOf(user) for c in coins]
    initial_eth_balance = boa.env.get_balance(user)

    with boa.env.prank(user):
        out = swap_with_deposit.remove_liquidity(
            token_amount, [0, 0, 0], use_eth
        )

    if use_eth:
        assert coins[2].balanceOf(user) == initial_coin_balances[2]
        assert (
            abs(boa.env.get_balance(user) - (initial_eth_balance + out[2]))
            == 0
        )
    else:
        assert boa.env.get_balance(user) == initial_eth_balance
        assert abs(coins[2].balanceOf(user) - out[2]) == 0


@given(
    frac=strategy("uint256", min_value=10**10, max_value=5 * 10**17),
    i=strategy("uint8", min_value=0, max_value=1),
    use_eth=strategy("bool"),
)
def test_remove_liquidity_one_coin_eth(
    swap_with_deposit, coins, user, frac, i, use_eth
):

    token_amount = swap_with_deposit.balanceOf(user) * frac // 10**18
    assert token_amount > 0

    initial_coin_balances = [c.balanceOf(user) for c in coins]
    initial_eth_balance = boa.env.get_balance(user)

    with boa.env.prank(user):
        swap_with_deposit.remove_liquidity_one_coin(
            token_amount, i, 0, use_eth
        )

    if i != 2 or not use_eth:
        assert coins[i].balanceOf(user) > initial_coin_balances[i]
        assert initial_eth_balance == boa.env.get_balance(user)
    else:
        assert boa.env.get_balance(user) > initial_eth_balance
        assert coins[i].balanceOf(user) == initial_coin_balances[i]

    for j in range(3):
        if i == j:
            continue
        assert coins[j].balanceOf(user) == initial_coin_balances[j]
