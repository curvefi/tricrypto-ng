from dataclasses import dataclass
from typing import List

import click
from ape import Contract, project  # noqa: F401
from ape.api.address import Address
from ape.cli import NetworkBoundCommand, account_option, network_option
from eth_abi import encode  # noqa: F401


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


# -------------- CURVE DATA --------------

MA_TIME = 866  # 600 seconds / ln(2)
# TODO: fetch pool params from mainnet tricrypto2 contract


@dataclass
class CurveDAO:
    ownership_admin: Address
    fee_receiver: Address


@dataclass
class PoolParams:
    name: str
    symbol: str
    coins: List[Address, Address, Address]
    implementation_index: int
    A: int
    gamma: int
    mid_fee: int
    out_fee: int
    allowed_extra_profit: int
    fee_gamma: int
    adjustment_step: int
    ma_time: int
    initial_prices: List[int]


curve_dao_network_settings = {
    "ethereum": CurveDAO(
        ownership_admin="0x40907540d8a6C65c637785e8f8B742ae6b0b9968",
        fee_receiver="0xeCb456EA5365865EbAb8a2661B0c503410e9B347",
        weth="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    ),
    "arbitrum": CurveDAO(
        ownership_admin="0xb055ebbacc8eefc166c169e9ce2886d0406ab49b",
        fee_receiver="0xd4f94d0aaa640bbb72b5eec2d85f6d114d81a88e",
        weth="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    ),
    "optimism": CurveDAO(
        ownership_admin="0xB055EbbAcc8Eefc166c169e9Ce2886D0406aB49b",
        fee_receiver="0xbF7E49483881C76487b0989CD7d9A8239B20CA41",
        weth="0x4200000000000000000000000000000000000006",
    ),
}


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(
    cls=NetworkBoundCommand,
)
@network_option()
@account_option()
def deploy(network, account):

    account.set_autosign(True)

    for _network, data in curve_dao_network_settings.items():

        if f":{_network}:" == network:

            owner = data.ownership_admin
            fee_receiver = data.fee_receiver
            weth = data.fee_receiver

    assert owner, f"Curve's DAO contracts may not be on {network}."

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
    constructor_args = [fee_receiver, owner, weth]
    factory = account.deploy(project.CurveTricryptoFactory, *constructor_args)
    print(
        "Constructor args:",
        encode(["address", "address", "address"], constructor_args).hex(),
    )

    factory.set_pool_implementation(amm_impl, 0, sender=account)
    factory.set_gauge_implementation(gauge_impl, sender=account)
    factory.set_views_implementation(views_contract, sender=account)
    factory.set_math_implementation(math_contract, sender=account)

    # ------------ DEPLOY POOL ------------

    pool = None
    assert pool

    print("Success!")
