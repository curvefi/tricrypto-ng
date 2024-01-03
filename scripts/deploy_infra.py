# flake8: noqa E501

import os
import sys

import boa
import deployment_utils as deploy_utils
import yaml
from boa.network import NetworkEnv
from eth.codecs.abi.exceptions import DecodeError
from eth_account import Account
from eth_utils import keccak
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
    calculated_address,
    create2deployer,
    network,
    abi_encoded_args=b"",
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
    salt = keccak(42069)
    compiled_bytecode = contract_obj.compiler_data.bytecode

    try:
        (
            precomputed_address,
            deployment_bytecode,
        ) = deploy_utils.get_create2_deployment_address(
            compiled_bytecode,
            abi_encoded_args,
            salt,
            create2deployer=create2deployer,
            blueprint=blueprint,
            blueprint_preamble=b"\xFE\x71\x00",
        )
        assert precomputed_address == calculated_address

        deploy_utils.deploy_via_create2_factory(
            deployment_bytecode,
            salt,
            create2deployer=create2deployer,
        )
        deployed_address = precomputed_address

    except DecodeError:

        logger.log(
            f"No create2deployer found for {network}. Deploying with CREATE."
        )
        if blueprint:
            c = contract_obj.deploy_as_blueprint()
        else:
            c = contract_obj.deploy()

        deployed_address = c.address

    logger.log(f"Deployed! At: {deployed_address}.")

    if upkeep_deploy_log:
        store_deployed_contract(
            network, contract_designation, str(deployed_address)
        )

    return contract_obj.at(deployed_address)


def deploy_infra(network, url, account, fork=False):

    logger.log(f"Deploying on {network} ...")

    if fork:
        boa.env.fork(url)
        logger.log("Forkmode ...")
        boa.env.eoa = deploy_utils.FIDDYDEPLOYER  # set eoa address here
    else:
        logger.log("Prodmode ...")
        boa.set_env(NetworkEnv(url))
        boa.env.add_account(Account.from_key(os.environ[account]))

    CREATE2DEPLOYER = boa.load_abi("abi/create2deployer.json").at(
        "0x13b0D85CcB8bf860b6b79AF3029fCA081AE9beF2"
    )


def main():

    forkmode = False
    deploy_infra(
        "ethereum:sepolia",
        os.environ["RPC_ETHEREUM_SEPOLIA"],
        "FIDDYDEPLOYER",
        fork=forkmode,
    )


if __name__ == "__main__":
    main()
