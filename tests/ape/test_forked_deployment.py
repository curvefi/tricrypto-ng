from ape import project


def get_deposit_amounts(amount_per_token_usd, initial_prices, coins):
    initial_prices = [10**18] + initial_prices
    precisions = [
        10 ** project.ERC20Mock.at(coin).decimals() for coin in coins
    ]
    deposit_amounts = [
        amount_per_token_usd * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


def test_add_liquidity_weth(swap, params, user, coins):

    tokens_to_add = get_deposit_amounts(20, params["initial_prices"], coins)
    tx = swap.add_liquidity(tokens_to_add, 0, False, sender=user)
    d_tokens = tx.return_value

    assert swap.balanceOf(user) == swap.totalSupply() == d_tokens


def test_add_liquidity_eth(swap, params, user, coins):

    tokens_to_add = get_deposit_amounts(20, params["initial_prices"], coins)
    tx = swap.add_liquidity(
        tokens_to_add,
        0,
        True,
        sender=user,
        value=tokens_to_add[2],
    )
    d_tokens = tx.return_value
    assert d_tokens > 0


def test_exchange_eth(swap, user, coins):

    amt_usdc_in = 10 * 10 ** project.ERC20Mock.at(coins[0]).decimals()
    tx = swap.exchange_underlying(0, 2, amt_usdc_in, 0, sender=user)
    dy_eth = tx.events.filter(swap.TokenExchange)[0].tokens_bought
    assert dy_eth > 0

    tx = swap.exchange_underlying(2, 0, dy_eth, 0, sender=user, value=dy_eth)
    dy_usdc = tx.events.filter(swap.TokenExchange)[0].tokens_bought
    assert dy_usdc > 0

    tx = swap.exchange(0, 1, dy_usdc * 2, 0, sender=user)
    dy_wbtc = tx.events.filter(swap.TokenExchange)[0].tokens_bought
    assert dy_wbtc > 0


def test_remove_liquidity_one_coin_eth(swap, user):

    eth_balance = user.balance
    bal = swap.balanceOf(user)
    amt_to_remove = int(bal / 4)

    tx = swap.remove_liquidity_one_coin(amt_to_remove, 2, 0, True, sender=user)
    dy_eth = tx.events.filter(swap.RemoveLiquidityOne)[0].coin_amount
    assert dy_eth > 0
    assert user.balance == eth_balance + dy_eth


def test_remove_liquidity_one_coin(swap, user, coins):

    for coin_id, coin in enumerate(coins):

        bal = swap.balanceOf(user)
        coin_contract = project.ERC20Mock.at(coin)
        coin_balance = coin_contract.balanceOf(user)

        tx = swap.remove_liquidity_one_coin(
            int(bal / 4), coin_id, 0, False, sender=user
        )  # noqa: E501

        dy_coin = tx.events.filter(swap.RemoveLiquidityOne)[0].coin_amount
        assert dy_coin > 0
        assert coin_contract.balanceOf(user) == coin_balance + dy_coin


def test_claim_admin_fees(swap, user, fee_receiver):

    fees_claimed = swap.balanceOf(fee_receiver)
    swap.claim_admin_fees(sender=user)
    if swap.totalSupply() < 10**18:
        assert swap.balanceOf(fee_receiver) == fees_claimed
    else:
        assert swap.balanceOf(fee_receiver) > fees_claimed


def test_remove_liquidity(swap, user):

    eth_balance = user.balance
    bal = swap.balanceOf(user)
    tx = swap.remove_liquidity(int(bal / 4), [0, 0, 0], True, sender=user)
    dy_tokens = tx.events.filter(swap.RemoveLiquidity)[0].token_amounts
    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    assert eth_balance + dy_tokens[2] == user.balance


def test_remove_liquidity_eth(swap, user):

    bal = swap.balanceOf(user)
    tx = swap.remove_liquidity(int(bal / 4), [0, 0, 0], False, sender=user)
    dy_tokens = tx.return_value

    for tkn_amt in dy_tokens:
        assert tkn_amt > 0
