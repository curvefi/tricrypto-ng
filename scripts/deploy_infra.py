# flake8: noqa E501

import os
import sys

import boa
import boa_zksync
import deployment_utils as deploy_utils
import yaml
from boa.network import NetworkEnv
from eth_account import Account
from rich.console import Console as RichConsole

logger = RichConsole(file=sys.stdout)


def check_contract_deployed(network, designation):

    with open("./deployments.yaml", "r") as file:
        deployments = yaml.safe_load(file)

    if (
        network in deployments.keys()
        and designation in deployments[network].keys()
    ):
        return deployments[network][designation]


def store_deployed_contract(network, designation, deployment_address):

    with open("./deployments.yaml", "r") as file:
        deployments = yaml.safe_load(file)

    if not network in deployments.keys():
        deployments[network] = {}

    deployments[network][designation] = deployment_address

    with open("./deployments.yaml", "w") as file:
        yaml.dump(deployments, file)


def check_and_deploy(
    contract_obj,
    contract_designation,
    ctor_args,
    network,
    blueprint: bool = False,
    upkeep_deploy_log: bool = False,
):

    deployed_contract_address = check_contract_deployed(
        network, contract_designation
    )
    if deployed_contract_address:
        logger.log(f"Contract exists at {deployed_contract_address} ...")
        return contract_obj.at(deployed_contract_address)

    logger.log(f"Deploying {contract_designation} contract ...")

    if blueprint:
        if not "zksync" in network:
            c = contract_obj.deploy_as_blueprint()
        else:
            # we need special deployment code for zksync
            packed_precisions = 340282366920938463463374607431768211457
            packed_gamma_A = 136112946768375385385349842972852284582400000
            packed_fee_params = 8847341539944400050877843276543133320576000000
            packed_rebalancing_params = (
                6125082604576892342340742933771827806226
            )
            c = contract_obj.deploy_as_blueprint(
                "Blueprint",  # _name
                "_",  # _symbol
                ["0x0000000000000000000000000000000000000000"] * 3,  # _coins
                "0x0000000000000000000000000000000000000000",  # _math
                "0x0000000000000000000000000000000000000000",  # _weth
                b"\1" * 32,  # _salt
                packed_precisions,
                packed_gamma_A,
                packed_fee_params,
                packed_rebalancing_params,
                1,  # initial_price
            )
    else:
        c = contract_obj.deploy(*ctor_args)

    deployed_address = c.address

    logger.log(f"Deployed! At: {deployed_address}.")

    if upkeep_deploy_log:
        store_deployed_contract(
            network, contract_designation, str(deployed_address)
        )

    return contract_obj.at(deployed_address)


def deploy_infra(network, url, account, fork=False):

    logger.log(f"Deploying on {network} ...")
    contract_folder = "main"

    if network == "zksync:mainnet":
        contract_folder = "zksync"
        if not fork:
            boa_zksync.set_zksync_env(url)
            logger.log("Prodmode on zksync Era ...")
        else:
            boa_zksync.set_zksync_fork(url)
            logger.log("Forkmode on zksync Era ...")

        boa.env.set_eoa(Account.from_key(os.environ[account]))

    else:

        if fork:
            boa.env.fork(url)
            logger.log("Forkmode ...")
            boa.env.eoa = deploy_utils.FIDDYDEPLOYER  # set eoa address here
        else:
            logger.log("Prodmode ...")
            boa.set_env(NetworkEnv(url))
            boa.env.add_account(Account.from_key(os.environ[account]))

    # we want to deploy both implementations. ETH transfers implementation
    # goes to idx 0, and the no native token transfer version goes to idx 1.

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:
            fee_receiver = data.fee_receiver_address

    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    # --------------------- Initialise contract objects ---------------------

    math_contract_obj = boa.load_partial(
        f"./contracts/{contract_folder}/CurveCryptoMathOptimized3.vy"
    )
    views_contract_obj = boa.load_partial(
        f"./contracts/{contract_folder}/CurveCryptoViews3Optimized.vy"
    )

    amm_contract_native_transfers_enabled_obj = boa.load_partial(
        f"./contracts/{contract_folder}/CurveTricryptoOptimizedWETH.vy"
    )
    amm_contract_native_transfers_disabled_obj = boa.load_partial(
        f"./contracts/{contract_folder}/CurveTricryptoOptimized.vy"
    )

    if network == "ethereum:mainnet":
        factory_contract_obj = boa.load_partial(
            "./contracts/main/CurveTricryptoFactory.vy"
        )
        logger.log("Using Mainnet tricrypto factory contract.")
    else:
        factory_contract_obj = boa.load_partial(
            f"./contracts/{contract_folder}/CurveL2TricryptoFactory.vy"
        )
        logger.log(
            "Using L2/sidechain (non-Ethereum mainnet) tricrypto factory contract."
        )

    # deploy non-blueprint contracts:
    math_contract = check_and_deploy(
        contract_obj=math_contract_obj,
        contract_designation="math",
        ctor_args=[],
        network=network,
        upkeep_deploy_log=not fork,
    )
    views_contract = check_and_deploy(
        contract_obj=views_contract_obj,
        contract_designation="views",
        network=network,
        ctor_args=[],
        upkeep_deploy_log=not fork,
    )

    # deploy blueprint:
    amm_native_transfers_enabled_blueprint = check_and_deploy(
        contract_obj=amm_contract_native_transfers_enabled_obj,
        contract_designation="amm_native_transfers_enabled",
        network=network,
        ctor_args=[],
        blueprint=True,
        upkeep_deploy_log=not fork,
    )
    if not network == "ethereum:mainnet":
        amm_native_transfers_disabled_blueprint = check_and_deploy(
            contract_obj=amm_contract_native_transfers_disabled_obj,
            contract_designation="amm_native_transfers_disabled",
            network=network,
            ctor_args=[],
            blueprint=True,
            upkeep_deploy_log=not fork,
        )

    # Factory:
    factory = check_and_deploy(
        contract_obj=factory_contract_obj,
        contract_designation="factory",
        network=network,
        ctor_args=[fee_receiver, deploy_utils.FIDDYDEPLOYER],
        upkeep_deploy_log=not fork,
    )

    if factory.admin() == deploy_utils.FIDDYDEPLOYER:
        # Set up implementation addresses in the factory.
        if (
            not factory.pool_implementations(0)
            == amm_native_transfers_enabled_blueprint.address
        ):
            logger.log(
                "Setting native transfers enabled AMM implementation at index 0 ..."
            )
            factory.set_pool_implementation(
                amm_native_transfers_enabled_blueprint.address, 0
            )

        if (
            not factory.pool_implementations(1)
            == amm_native_transfers_disabled_blueprint.address
        ):
            logger.log(
                "Setting native transfers disabled AMM implementation at index 1 ..."
            )
            factory.set_pool_implementation(
                amm_native_transfers_disabled_blueprint.address, 1
            )

        if not factory.views_implementation() == views_contract.address:
            logger.log("Setting Views implementation ...")
            factory.set_views_implementation(views_contract.address)

        if not factory.math_implementation() == math_contract.address:
            logger.log("Setting Math implementation ...")
            factory.set_math_implementation(math_contract.address)

    else:

        logger.log(
            "Cannot set implementation addresses on Factory as deployer is not admin."
        )

    logger.log("Infra deployed!")


def main():

    forkmode = False
    deployer = "FIDDYDEPLOYER"
    network = "zksync:mainnet"
    rpc = "https://mainnet.era.zksync.io"
    deploy_infra(
        network=network,
        url=rpc,
        account=deployer,
        fork=forkmode,
    )


if __name__ == "__main__":
    main()
