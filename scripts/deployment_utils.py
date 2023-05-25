import math
from dataclasses import dataclass

import click
from ape import Contract, networks, project
from ape.api.address import Address
from ape.logging import logger
from eth_abi import encode
from pycoingecko import CoinGeckoAPI

DOLLAR_VALUE_OF_TOKENS_TO_DEPOSIT = 20


def _get_tx_params():

    if "mainnet-fork" == networks.active_provider.network.name:
        return {}

    if "sepolia" == networks.active_provider.network.name:
        return {}

    active_provider = networks.active_provider
    max_fee = active_provider.base_fee * 2
    max_priority_fee = int(0.5e9)

    return {"max_fee": max_fee, "max_priority_fee": max_priority_fee}


def deploy_blueprint(contract, account):

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
        **_get_tx_params(),
    )
    receipt = account.call(tx)
    click.echo(f"blueprint deployed at: {receipt.contract_address}")
    return receipt.contract_address


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


# -------------- CURVE DATA --------------


@dataclass
class CurveNetworkSettings:
    dao_ownership_contract: Address
    fee_receiver_address: Address
    usdc_address: Address
    wbtc_address: Address
    weth_address: Address


GAUGE_CONTROLLER = "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB"
ADDRESS_PROVIDER = "0x0000000022d53366457f9d5e68ec105046fc4383"


curve_dao_network_settings = {
    "ethereum:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0x40907540d8a6C65c637785e8f8B742ae6b0b9968",
        fee_receiver_address="0xeCb456EA5365865EbAb8a2661B0c503410e9B347",
        usdc_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        wbtc_address="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        weth_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    ),
    "ethereum:sepolia": CurveNetworkSettings(
        dao_ownership_contract="0xE6DA683076b7eD6ce7eC972f21Eb8F91e9137a17",
        fee_receiver_address="0xE6DA683076b7eD6ce7eC972f21Eb8F91e9137a17",
        usdc_address="0x51fCe89b9f6D4c530698f181167043e1bB4abf89",
        wbtc_address="0xFF82bB6DB46Ad45F017e2Dfb478102C7671B13b3",
        weth_address="0xf531B8F309Be94191af87605CfBf600D71C2cFe0",
    ),
    "arbitrum:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
        fee_receiver_address="0xd4f94d0aaa640bbb72b5eec2d85f6d114d81a88e",
        usdc_address="0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
        wbtc_address="0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",
        weth_address="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    ),
    "optimism:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver_address="0xbF7E49483881C76487b0989CD7d9A8239B20CA41",
        usdc_address="0x7f5c764cbc14f9669b88837ca1490cca17c31607",
        wbtc_address="0x68f180fcce6836688e9084f035309e29bf0a2095",
        weth_address="0x4200000000000000000000000000000000000006",
    ),
    "polygon:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver_address="0x774D1Dba98cfBD1F2Bc3A1F59c494125e07C48F9",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wbtc_address="0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        weth_address="0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    ),
    "avalanche:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0xbabe61887f1de2713c6f97e567623453d3c79f67",
        fee_receiver_address="0x06534b0BF7Ff378F162d4F348390BDA53b15fA35",
        usdc_address="0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        wbtc_address="0x50b7545627a5162F82A992c33b87aDc75187B218",
        weth_address="0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB",
    ),
    "gnosis:mainnet": CurveNetworkSettings(
        dao_ownership_contract="",  # <--- need to deploy sidechain ownership contract  # noqa: E501
        fee_receiver_address="",  # <--- need to deploy sidechain pool proxy
        usdc_address="0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
        wbtc_address="0x8e5bBbb09Ed1ebdE8674Cda39A0c169401db4252",
        weth_address="0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1",
    ),
    "fantom:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",  # <--- thin proxy  # noqa: E501
        fee_receiver_address="0x2B039565B2b7a1A9192D4847fbd33B25b836B950",
        usdc_address="0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # <-- multichain usdc  # noqa: E501
        wbtc_address="0x321162Cd933E2Be498Cd2267a90534A804051b11",  # <-- multichain wbtc  # noqa: E501
        weth_address="0x74b23882a30290451A17c44f4F05243b6b58C76d",  # <-- multichain weth  # noqa: E501
    ),
    "celo:mainnet": CurveNetworkSettings(
        dao_ownership_contract="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- needs to accept transfer ownership for 0x5277A0226d10392295E8D383E9724D6E416d6e6C  # noqa: E501
        fee_receiver_address="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- Thin proxy, needs to be changed!  # noqa: E501
        usdc_address="0x37f750b7cc259a2f741af45294f6a16572cf5cad",  # <-- wormhole usdc  # noqa: E501
        wbtc_address="",
        weth_address="0x66803FB87aBd4aaC3cbB3fAd7C3aa01f6F3FB207",  # <-- wormhole weth  # noqa: E501
    ),
    "kava:mainnet": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc_address="",
        wbtc_address="",
        weth_address="",
    ),
    "moonbeam": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc_address="",
        wbtc_address="",
        weth_address="",
    ),
    "aurora": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc_address="0xb12bfca5a55806aaf64e99521918a4bf0fc40802",
        wbtc_address="",
        weth_address="",
    ),
}


CURVE_DAO_OWNERSHIP = {
    "agent": "0x40907540d8a6c65c637785e8f8b742ae6b0b9968",
    "voting": "0xe478de485ad2fe566d49342cbd03e49ed7db3356",
    "token": "0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2",
    "quorum": 30,
}


def get_tricrypto_usdc_params():

    cg = CoinGeckoAPI()
    TOKEN_PRICES = []
    for coin in ["usd-coin", "wrapped-bitcoin", "ethereum"]:
        TOKEN_PRICES.append(
            cg.get_price(ids=coin, vs_currencies="usd")[coin]["usd"]
        )
    USDC_PRICE = TOKEN_PRICES[0]
    INITIAL_PRICES = [int(p / USDC_PRICE) * 10**18 for p in TOKEN_PRICES[1:]]
    MA_TIME_SECONDS = 600  # seconds
    return {
        "name": "TricryptoUSDC",
        "symbol": "crvUSDCWBTCWETH",
        "coins": [],
        "implementation_index": 0,
        "A": 1707629,
        "gamma": 11809167828997,
        "mid_fee": 3000000,
        "out_fee": 30000000,
        "allowed_extra_profit": 2000000000000,
        "fee_gamma": 500000000000000,
        "adjustment_step": 490000000000000,
        "ma_time": int(MA_TIME_SECONDS / math.log(2)),
        "initial_prices": INITIAL_PRICES,
    }


def test_deployment(pool, coins, fee_receiver, account):

    PARAMS = get_tricrypto_usdc_params()

    logger.info(
        "------------ TEST IF CONTRACT WORKS AS INTENDED IN PROD ----------------"  # noqa: E501
    )

    for coin in coins:
        coin_contract = Contract(coin)
        bal = coin_contract.balanceOf(account)
        assert bal > 0, "Not enough coins!"

        if coin_contract.allowance(account, pool) > 0:
            continue

        coin_name = coin_contract.name()
        logger.info(f"Approve pool to spend deployer's {coin_name}:")

        coin_contract.approve(pool, bal, sender=account, **_get_tx_params())

    logger.info("------------------------------ Add liquidity")

    logger.info("Deposit WETH with other tokens:")
    tokens_to_add = get_deposit_amounts(
        DOLLAR_VALUE_OF_TOKENS_TO_DEPOSIT, PARAMS["initial_prices"], coins
    )

    logger.info(f"Add {tokens_to_add} tokens to deployed pool: ")

    tx = pool.add_liquidity(
        tokens_to_add, 0, False, sender=account, **_get_tx_params()
    )
    d_tokens = tx.return_value
    assert pool.balanceOf(account) == pool.totalSupply() == d_tokens
    logger.info(f"Received {d_tokens} number of LP Tokens.")

    logger.info("Deposit ETH with other tokens:")
    tx = pool.add_liquidity(
        tokens_to_add,
        0,
        True,
        sender=account,
        value=tokens_to_add[2],
        **_get_tx_params(),
    )
    d_tokens = tx.return_value
    assert d_tokens > 0
    logger.info(f"Received {d_tokens} number of LP Tokens.")

    logger.info("------------------------------ Exchange")

    amt_usdc_in = 10 * 10 ** project.ERC20Mock.at(coins[0]).decimals()
    logger.info(f"Test exchange_underlying of {amt_usdc_in} USDC -> ETH:")
    tx = pool.exchange_underlying(
        0, 2, amt_usdc_in, 0, sender=account, **_get_tx_params()
    )
    dy_eth = tx.events.filter(pool.TokenExchange)[
        0
    ].tokens_bought  # return_value is broken in ape somehow
    assert dy_eth > 0
    logger.info(f"Received {dy_eth} ETH")

    logger.info(f"Test exchange_underlying of {dy_eth} ETH -> USDC:")
    tx = pool.exchange_underlying(
        2, 0, dy_eth, 0, sender=account, value=dy_eth, **_get_tx_params()
    )
    dy_usdc = tx.events.filter(pool.TokenExchange)[0].tokens_bought
    assert dy_usdc > 0
    logger.info(f"Received {dy_usdc} USDC")

    logger.info(f"Test exchange of {dy_usdc} USDC -> WBTC:")
    tx = pool.exchange(
        0, 1, dy_usdc * 2, 0, sender=account, **_get_tx_params()
    )
    dy_wbtc = tx.events.filter(pool.TokenExchange)[0].tokens_bought
    assert dy_wbtc > 0
    logger.info(f"Received {dy_wbtc} WBTC")

    logger.info("------------------------------ Remove Liquidity in one coin")

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    amt_to_remove = int(bal / 4)
    logger.info(f"Remove {amt_to_remove} liquidity in native token (ETH):")
    tx = pool.remove_liquidity_one_coin(
        amt_to_remove, 2, 0, True, sender=account, **_get_tx_params()
    )
    dy_eth = tx.events.filter(pool.RemoveLiquidityOne)[0].coin_amount
    assert dy_eth > 0
    assert account.balance == eth_balance + dy_eth
    logger.info(f"Removed {dy_eth} of ETH.")

    for coin_id, coin in enumerate(coins):

        bal = pool.balanceOf(account)
        coin_contract = project.ERC20Mock.at(coin)
        coin_name = coin_contract.name()
        coin_balance = coin_contract.balanceOf(account)

        logger.info(f"Remove {int(bal/4)} liquidity in {coin_name}:")
        tx = pool.remove_liquidity_one_coin(
            int(bal / 4), coin_id, 0, False, sender=account, **_get_tx_params()
        )  # noqa: E501

        dy_coin = tx.events.filter(pool.RemoveLiquidityOne)[0].coin_amount
        assert dy_coin > 0
        assert coin_contract.balanceOf(account) == coin_balance + dy_coin
        logger.info(f"Removed {dy_coin} of {coin_name}.")

    logger.info("------------------------------ Claim admin fees")
    logger.info("(should not claim since pool hasn't accrued enough profits)")

    fees_claimed = pool.balanceOf(fee_receiver)
    pool.claim_admin_fees(sender=account, **_get_tx_params())
    if pool.totalSupply() < 10**18:
        assert pool.balanceOf(fee_receiver) == fees_claimed
        logger.info("No fees claimed.")
    else:
        assert pool.balanceOf(fee_receiver) > fees_claimed
        logger.info(
            f"{pool.balanceOf(fee_receiver) - fees_claimed} LP tokens of admin fees claimed!"  # noqa: E501
        )

    logger.info(
        "------------------------------ Remove liquidity proportionally"
    )

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    logger.info(
        f"Remove {int(bal/4)} amount of liquidity proportionally (with native ETH):"  # noqa: E501
    )
    tx = pool.remove_liquidity(
        int(bal / 4), [0, 0, 0], True, sender=account, **_get_tx_params()
    )
    dy_tokens = tx.events.filter(pool.RemoveLiquidity)[0].token_amounts
    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    logger.info(f"Removed {dy_tokens} of liquidity.")

    assert eth_balance + dy_tokens[2] == account.balance

    logger.info(
        f"Remove {int(bal/4)} amount of liquidity proportionally (with native ETH):"  # noqa: E501
    )
    tx = pool.remove_liquidity(
        int(bal / 4), [0, 0, 0], False, sender=account, **_get_tx_params()
    )
    dy_tokens = tx.return_value

    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    logger.info("Successfully tested deployment!")


def deploy_amm_factory(account, fee_receiver, weth, deployed_contracts={}):

    if "math" not in deployed_contracts:
        logger.info("Deploying math contract:")
        math_contract = account.deploy(
            project.CurveCryptoMathOptimized3, **_get_tx_params()
        )
    else:
        math_contract = project.CurveCryptoMathOptimized3.at(
            deployed_contracts["math"]
        )

    if "views" not in deployed_contracts:
        logger.info("Deploying views contract:")
        views_contract = account.deploy(
            project.CurveCryptoViews3Optimized, **_get_tx_params()
        )
    else:
        views_contract = project.CurveCryptoViews3Optimized.at(
            deployed_contracts["views"]
        )

    if "amm_impl" not in deployed_contracts:
        logger.info("Deploying AMM blueprint contract:")
        amm_impl = deploy_blueprint(
            project.CurveTricryptoOptimizedWETH, account
        )
    else:
        amm_impl = project.CurveTricryptoOptimizedWETH.at(
            deployed_contracts["amm_impl"]
        )

    if "factory" not in deployed_contracts:
        logger.info("Deploy factory:")
        factory = project.CurveTricryptoFactory.deploy(
            fee_receiver,
            account.address,
            sender=account,
            **_get_tx_params(),
        )
        constructor_args = [fee_receiver, account.address, weth]
        logger.info(
            f"Constructor args: {encode(['address', 'address', 'address'], constructor_args).hex()}\n"  # noqa: E501
        )
    else:
        factory = project.CurveTricryptoFactory.at(
            deployed_contracts["factory"]
        )

    logger.info("Set Pool Implementation:")
    factory.set_pool_implementation(
        amm_impl, 0, sender=account, **_get_tx_params()
    )

    logger.info("Set Views implementation:")
    factory.set_views_implementation(
        views_contract, sender=account, **_get_tx_params()
    )

    logger.info("Set Math implementation:")
    factory.set_math_implementation(
        math_contract, sender=account, **_get_tx_params()
    )

    return factory
