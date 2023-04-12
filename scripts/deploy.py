import math
from dataclasses import dataclass

import click
from ape import Contract, project
from ape.api.address import Address
from ape.cli import NetworkBoundCommand, account_option, network_option
from eth_abi import encode
from pycoingecko import CoinGeckoAPI


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
    )
    tx.gas_limit = project.provider.estimate_gas_cost(tx)
    tx = account.sign_transaction(tx)
    receipt = project.provider.send_transaction(tx)
    click.echo(f"blueprint deployed at: {receipt.contract_address}")
    return receipt.contract_address


def get_deposit_amounts(amount_per_token_usd, initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

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


# coingecko prices:
cg = CoinGeckoAPI()
TOKEN_PRICES = []
for coin in ["usd-coin", "wrapped-bitcoin", "ethereum"]:
    TOKEN_PRICES.append(
        cg.get_price(ids=coin, vs_currencies="usd")[coin]["usd"]
    )
USDC_PRICE = TOKEN_PRICES[0]
INITIAL_PRICES = [int(p / USDC_PRICE) * 10**18 for p in TOKEN_PRICES[1:]]
MA_TIME_SECONDS = 600  # seconds
PARAMS = {
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


curve_dao_network_settings = {
    "ethereum": CurveNetworkSettings(
        ownership_admin="0x40907540d8a6C65c637785e8f8B742ae6b0b9968",
        fee_receiver="0xeCb456EA5365865EbAb8a2661B0c503410e9B347",
        usdc="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        wbtc="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        weth="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    ),
    "arbitrum": CurveNetworkSettings(
        ownership_admin="0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
        fee_receiver="0xd4f94d0aaa640bbb72b5eec2d85f6d114d81a88e",
        usdc="0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
        wbtc="0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",
        weth="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    ),
    "optimism": CurveNetworkSettings(
        ownership_admin="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver="0xbF7E49483881C76487b0989CD7d9A8239B20CA41",
        usdc="0x7f5c764cbc14f9669b88837ca1490cca17c31607",
        wbtc="0x68f180fcce6836688e9084f035309e29bf0a2095",
        weth="0x4200000000000000000000000000000000000006",
    ),
    "polygon": CurveNetworkSettings(
        ownership_admin="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver_address="0x774D1Dba98cfBD1F2Bc3A1F59c494125e07C48F9",
        usdc="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wbtc="0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        weth="0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    ),
    "avalanche": CurveNetworkSettings(
        ownership_admin="0xbabe61887f1de2713c6f97e567623453d3c79f67",
        fee_receiver_address="0x06534b0BF7Ff378F162d4F348390BDA53b15fA35",
        usdc="0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        wbtc="0x50b7545627a5162F82A992c33b87aDc75187B218",
        weth="0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB",
    ),
    "gnosis": CurveNetworkSettings(
        dao_ownership_contract="",  # <--- need to deploy sidechain ownership contract  # noqa: E501
        fee_receiver_address="",  # <--- need to deploy sidechain pool proxy
        usdc="0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
        wbtc="0x8e5bBbb09Ed1ebdE8674Cda39A0c169401db4252",
        weth="0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1",
    ),
    "fantom": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",  # <--- thin proxy  # noqa: E501
        fee_receiver_address="0x2B039565B2b7a1A9192D4847fbd33B25b836B950",
        usdc="0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # <-- multichain usdc  # noqa: E501
        wbtc="0x321162Cd933E2Be498Cd2267a90534A804051b11",  # <-- multichain wbtc  # noqa: E501
        weth="0x74b23882a30290451A17c44f4F05243b6b58C76d",  # <-- multichain weth  # noqa: E501
    ),
    "celo": CurveNetworkSettings(
        dao_ownership_contract="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- needs to accept transfer ownership for 0x5277A0226d10392295E8D383E9724D6E416d6e6C  # noqa: E501
        fee_receiver_address="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- Thin proxy, needs to be changed!  # noqa: E501
        usdc="0x37f750b7cc259a2f741af45294f6a16572cf5cad",  # <-- wormhole usdc  # noqa: E501
        wbtc="",
        weth="0x66803FB87aBd4aaC3cbB3fAd7C3aa01f6F3FB207",  # <-- wormhole weth  # noqa: E501
    ),
    "kava": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc="",
        wbtc="",
        weth="",
    ),
    "moonbeam": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc="",
        wbtc="",
        weth="",
    ),
    "aurora": CurveNetworkSettings(
        dao_ownership_contract="",
        fee_receiver_address="",
        usdc="0xb12bfca5a55806aaf64e99521918a4bf0fc40802",
        wbtc="",
        weth="",
    ),
}


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy(network, account):

    account.set_autosign(True)

    for _network, data in curve_dao_network_settings.items():

        if f":{_network}:" == network:

            owner = data.ownership_admin
            fee_receiver = data.fee_receiver
            weth = data.fee_receiver
            coins = [data.usdc, data.wbtc, data.weth]
            PARAMS["coins"] = coins

    assert owner, f"Curve's DAO contracts may not be on {network}."
    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    # ------------ DEPLOY MAIN + AUXILIARY CONTRACTS ------------

    print("Deploying math contract")
    math_contract = account.deploy(project.CurveCryptoMathOptimized3)

    print("Deploying views contract")
    views_contract = account.deploy(project.CurveCryptoViews3Optimized)

    print("Deploying AMM blueprint contract")
    amm_impl = deploy_blueprint(project.CurveTricryptoOptimizedWETH, account)

    print("Deploying gauge blueprint contract")
    gauge_impl = deploy_blueprint(project.LiquidityGauge, account)

    # ------------ DEPLOY FACTORY ------------

    print("Deploy factory")
    constructor_args = [fee_receiver, account, weth]
    factory = account.deploy(project.CurveTricryptoFactory, *constructor_args)
    print(
        "Constructor args:",
        encode(["address", "address", "address"], constructor_args).hex(),
    )

    factory.set_pool_implementation(amm_impl, 0, sender=account)
    factory.set_gauge_implementation(gauge_impl, sender=account)
    factory.set_views_implementation(views_contract, sender=account)
    factory.set_math_implementation(math_contract, sender=account)

    # -------- TRANSFER FACTORY OWNERSHIP TO THE APPROPRIATE ENTITY ----------

    factory.commit_transfer_ownership(owner, sender=account)

    # ------------ DEPLOY POOL ------------

    print("Deploying Pool")
    pool = factory.deploy_pool(**PARAMS, sender=account)
    print(f"Success Deployed pool at {pool}!")

    # ------------ TEST IF CONTRACT WORKS AS INTENDED IN PROD ----------------

    for coin in coins:
        coin_contract = Contract(coin)
        bal = coin_contract.balanceOf(account) > 0

        assert bal > 0, "Not enough coins!"

        # Approve pool to spend deployer's coins
        coin_contract.approve(pool, bal, sender=account)

    # ------------------------------ Add liquidity

    # weth
    tokens_to_add = get_deposit_amounts(10, INITIAL_PRICES, coins)
    d_tokens = pool.add_liquidity(tokens_to_add, 0, False, sender=account)

    assert pool.balanceOf(account) == pool.totalSupply() == d_tokens

    # eth
    d_tokens = pool.add_liquidity(tokens_to_add, 0, True, sender=account)
    assert d_tokens > 0

    # ------------------------------ Exchange

    dy_eth = pool.exchange_underlying(0, 2, 10, 0, sender=account)
    assert dy_eth > 0

    dy_usdc = pool.exchange_underlying(2, 0, dy_eth, 0, sender=account)
    assert dy_usdc > 0

    dy_wbtc = pool.exchange(0, 1, dy_usdc, 0, sender=account)
    assert dy_wbtc > 0

    # ------------------------------ Remove Liquidity in one coin

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    dy_eth = pool.remove_liquidity_one_coin(
        int(bal / 4), 2, 0, True, sender=account
    )
    assert dy_eth > 0
    assert account.balance == eth_balance + dy_eth

    # ------------------------------ Claim admin fees (should borg)

    fees_claimed = pool.balanceOf(fee_receiver)
    pool.claim_admin_fees(sender=account)
    if pool.totalSupply() < 10**18:
        assert pool.balanceOf(fee_receiver) == fees_claimed
    else:
        assert pool.balanceOf(fee_receiver) > fees_claimed

    # ------------------------------ Remove liquidity proportionally

    eth_balance = account.balance
    bal = pool.balanceOf(account)
    dy_tokens = pool.remove_liquidity(int(bal / 4), [0, 0, 0], True)

    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    assert eth_balance + dy_tokens[2] == account.balance

    dy_tokens = pool.remove_liquidity(int(bal / 4), [0, 0, 0], False)

    for tkn_amt in dy_tokens:
        assert tkn_amt > 0

    print("Successfully tested deployment!")

    # ------------ CREATE VOTE FOR THE DAO TO ACCEPT OWNERSHIP OF NEW CONTRACTS -----  # noqa: E501
    # Now that the deployment is good, the DAO needs to accept ownership transfer  # noqa: E501
