import math
from dataclasses import dataclass

import click
from ape import Contract, project
from ape.api.address import Address
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
    receipt = account.call(tx)
    click.echo(f"blueprint deployed at: {receipt.contract_address}")
    return receipt.contract_address


def get_deposit_amounts(amount_per_token_usd, initial_prices, coins):
    initial_prices = [10**18] + initial_prices
    precisions = [10 ** Contract(coin).decimals() for coin in coins]
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
    "ethereum": CurveNetworkSettings(
        dao_ownership_contract="0x40907540d8a6C65c637785e8f8B742ae6b0b9968",
        fee_receiver_address="0xeCb456EA5365865EbAb8a2661B0c503410e9B347",
        usdc_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        wbtc_address="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        weth_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    ),
    "arbitrum": CurveNetworkSettings(
        dao_ownership_contract="0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
        fee_receiver_address="0xd4f94d0aaa640bbb72b5eec2d85f6d114d81a88e",
        usdc_address="0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
        wbtc_address="0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",
        weth_address="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    ),
    "optimism": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver_address="0xbF7E49483881C76487b0989CD7d9A8239B20CA41",
        usdc_address="0x7f5c764cbc14f9669b88837ca1490cca17c31607",
        wbtc_address="0x68f180fcce6836688e9084f035309e29bf0a2095",
        weth_address="0x4200000000000000000000000000000000000006",
    ),
    "polygon": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver_address="0x774D1Dba98cfBD1F2Bc3A1F59c494125e07C48F9",
        usdc_address="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        wbtc_address="0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        weth_address="0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    ),
    "avalanche": CurveNetworkSettings(
        dao_ownership_contract="0xbabe61887f1de2713c6f97e567623453d3c79f67",
        fee_receiver_address="0x06534b0BF7Ff378F162d4F348390BDA53b15fA35",
        usdc_address="0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        wbtc_address="0x50b7545627a5162F82A992c33b87aDc75187B218",
        weth_address="0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB",
    ),
    "gnosis": CurveNetworkSettings(
        dao_ownership_contract="",  # <--- need to deploy sidechain ownership contract  # noqa: E501
        fee_receiver_address="",  # <--- need to deploy sidechain pool proxy
        usdc_address="0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
        wbtc_address="0x8e5bBbb09Ed1ebdE8674Cda39A0c169401db4252",
        weth_address="0x6A023CCd1ff6F2045C3309768eAd9E68F978f6e1",
    ),
    "fantom": CurveNetworkSettings(
        dao_ownership_contract="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",  # <--- thin proxy  # noqa: E501
        fee_receiver_address="0x2B039565B2b7a1A9192D4847fbd33B25b836B950",
        usdc_address="0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # <-- multichain usdc  # noqa: E501
        wbtc_address="0x321162Cd933E2Be498Cd2267a90534A804051b11",  # <-- multichain wbtc  # noqa: E501
        weth_address="0x74b23882a30290451A17c44f4F05243b6b58C76d",  # <-- multichain weth  # noqa: E501
    ),
    "celo": CurveNetworkSettings(
        dao_ownership_contract="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- needs to accept transfer ownership for 0x5277A0226d10392295E8D383E9724D6E416d6e6C  # noqa: E501
        fee_receiver_address="0x56bc95Ded2BEF162131905dfd600F2b9F1B380a4",  # <-- Thin proxy, needs to be changed!  # noqa: E501
        usdc_address="0x37f750b7cc259a2f741af45294f6a16572cf5cad",  # <-- wormhole usdc  # noqa: E501
        wbtc_address="",
        weth_address="0x66803FB87aBd4aaC3cbB3fAd7C3aa01f6F3FB207",  # <-- wormhole weth  # noqa: E501
    ),
    "kava": CurveNetworkSettings(
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
