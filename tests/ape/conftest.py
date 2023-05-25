import pytest

try:
    from ape import Contract
except ImportError:
    print("Cannot find ape: install ape!")


@pytest.fixture(scope="module")
def deployer(accounts):
    return accounts[0]


@pytest.fixture(scope="module")
def owner(accounts):
    return accounts[1]


@pytest.fixture(scope="module")
def fee_receiver(accounts):
    return accounts[2]


@pytest.fixture(scope="module")
def user(accounts):
    # impersonate Avalanche bridge:
    return accounts["0x8EB8a3b98659Cce290402893d0123abb75E3ab28"]


# ------ token fixtures -------


@pytest.fixture(scope="module")
def weth():
    return Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture(scope="module")
def wbtc():
    return Contract("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")


@pytest.fixture(scope="module")
def usdt():
    return Contract("0xdac17f958d2ee523a2206206994597c13d831ec7")


@pytest.fixture(scope="module")
def coins(weth, wbtc, usdt):
    return [usdt, wbtc, weth]


def _get_deposit_amounts(amount_per_token_usd, initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

    deposit_amounts = [
        amount_per_token_usd * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


# ------ deploy legacy ------


@pytest.fixture(scope="module")
def token_legacy():
    token = Contract("0xc4ad29ba4b3c580e6d59105fff484999997675ff")
    return token


@pytest.fixture(scope="module")
def swap_legacy(coins, user, token_legacy, project):
    swap = Contract("0xd51a44d3fae010294c616388b506acda1bfaae46")
    for coin in coins:
        coin.approve(swap, 2**256 - 1, sender=user)

    price_oracle = [10**18, swap.price_oracle(0), swap.price_oracle(1)]
    amounts = _get_deposit_amounts(10**6, price_oracle, coins)
    swap.add_liquidity(amounts, 0, sender=user)

    return swap


# --------------- optimised tricrypto deployment ----------------


def deploy_blueprint(contract, account, project):
    initcode = contract.contract_type.deployment_bytecode.bytecode
    if isinstance(initcode, str):
        initcode = bytes.fromhex(initcode.removeprefix("0x"))
    initcode = b"\xfe\x71\x00" + initcode  # eip-5202 preamble version 0
    initcode = (
        b"\x61"
        + len(initcode).to_bytes(2, "big")
        + b"\x3d\x81\x60\x0a\x3d\x39\xf3"
        + initcode
    )
    tx = project.provider.network.ecosystem.create_transaction(
        chain_id=project.provider.chain_id,
        data=initcode,
        gas_price=project.provider.gas_price,
        nonce=account.nonce,
    )
    tx.gas_limit = project.provider.estimate_gas_cost(tx)
    tx = account.sign_transaction(tx)
    receipt = project.provider.send_transaction(tx)

    return receipt.contract_address


@pytest.fixture(scope="module")
def factory(deployer, fee_receiver, owner, weth, project):

    amm_blueprint = deploy_blueprint(
        project.CurveTricryptoOptimizedWETH, deployer, project
    )
    gauge_blueprint = deploy_blueprint(
        project.LiquidityGauge, deployer, project
    )

    math_contract = project.CurveCryptoMathOptimized3.deploy(sender=deployer)
    views_contract = project.CurveCryptoViews3Optimized.deploy(sender=deployer)

    factory = project.CurveTricryptoFactory.deploy(
        fee_receiver, owner, sender=deployer
    )

    factory.set_pool_implementation(amm_blueprint, 0, sender=owner)
    factory.set_gauge_implementation(gauge_blueprint, sender=owner)
    factory.set_views_implementation(views_contract, sender=owner)
    factory.set_math_implementation(math_contract, sender=owner)

    return factory


@pytest.fixture(scope="module")
def params(swap_legacy):

    initial_prices = [swap_legacy.price_scale(0), swap_legacy.price_scale(1)]

    ma_time = 866  # 600 seconds / ln(2)
    return {
        "A": swap_legacy.A(),
        "gamma": swap_legacy.gamma(),
        "mid_fee": swap_legacy.mid_fee(),
        "out_fee": swap_legacy.out_fee(),
        "allowed_extra_profit": swap_legacy.allowed_extra_profit(),
        "fee_gamma": swap_legacy.fee_gamma(),
        "adjustment_step": swap_legacy.adjustment_step(),
        "ma_time": ma_time,
        "initial_prices": initial_prices,
    }


@pytest.fixture(scope="module")
def swap(deployer, factory, coins, params, project, weth):

    tx = factory.deploy_pool(
        "Curve.fi USDC-BTC-ETH",
        "USDCBTCETH",
        [coin.address for coin in coins],
        weth,
        0,  # <-------- 0th implementation index
        params["A"],
        params["gamma"],
        params["mid_fee"],
        params["out_fee"],
        params["fee_gamma"],
        params["allowed_extra_profit"],
        params["adjustment_step"],
        params["ma_time"],
        params["initial_prices"],
        sender=deployer,
    )
    emitted_events = tx.decode_logs()
    pool_address = emitted_events[1].pool
    pool = project.CurveTricryptoOptimizedWETH.at(pool_address)
    return pool


@pytest.fixture(scope="module")
def swap_optimised(swap, user):

    for coin in coins:
        coin.approve(swap, 2**256 - 1, sender=user)

    amounts = _get_deposit_amounts(
        10**6, [10**18] + params["initial_prices"], coins
    )
    swap.add_liquidity(amounts, 0, False, sender=user)

    return swap
