import warnings

import click
from ape import Contract, project
from ape.cli import NetworkBoundCommand, account_option, network_option
from ape.logging import logger
from eth_abi import encode
from eth_utils import to_checksum_address

import scripts.deployment_utils as deploy_utils
from scripts.simulate import simulate
from scripts.vote_utils import make_vote

warnings.filterwarnings("ignore")


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_ethereum(network, account):

    assert "ethereum" in network

    is_sim = "mainnet-fork" in network
    PARAMS = deploy_utils.get_tricrypto_usdc_params()

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract
            fee_receiver = data.fee_receiver_address
            coins = [
                to_checksum_address(data.usdc_address),
                to_checksum_address(data.wbtc_address),
                to_checksum_address(data.weth_address),
            ]
            weth = coins[2]
            PARAMS["coins"] = coins

    assert owner, f"Curve's DAO contracts may not be on {network}."
    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    logger.info("Deploying math contract:")
    math_contract = account.deploy(project.CurveCryptoMathOptimized3)

    logger.info("Deploying views contract:")
    views_contract = account.deploy(project.CurveCryptoViews3Optimized)

    logger.info("Deploying AMM blueprint contract:")
    amm_impl = deploy_utils.deploy_blueprint(
        project.CurveTricryptoOptimizedWETH, account
    )

    logger.info("Deploying gauge blueprint contract:")
    gauge_impl = deploy_utils.deploy_blueprint(project.LiquidityGauge, account)

    logger.info("Deploy factory:")
    constructor_args = [fee_receiver, account.address, weth]
    factory = account.deploy(project.CurveTricryptoFactory, *constructor_args)
    logger.info(
        f"Constructor args: {encode(['address', 'address', 'address'], constructor_args).hex()}\n"  # noqa: E501
    )

    logger.info("Set Pool Implementation:")
    factory.set_pool_implementation(amm_impl, 0, sender=account)

    logger.info("Set Gauge Implementation:")
    factory.set_gauge_implementation(gauge_impl, sender=account)

    logger.info("Set Views implementation:")
    factory.set_views_implementation(views_contract, sender=account)

    logger.info("Set Math implementation:")
    factory.set_math_implementation(math_contract, sender=account)

    logger.info("Deploying Pool:")
    tx = factory.deploy_pool(
        PARAMS["name"],
        PARAMS["symbol"],
        PARAMS["coins"],
        PARAMS["implementation_index"],
        PARAMS["A"],
        PARAMS["gamma"],
        PARAMS["mid_fee"],
        PARAMS["out_fee"],
        PARAMS["fee_gamma"],
        PARAMS["allowed_extra_profit"],
        PARAMS["adjustment_step"],
        PARAMS["ma_time"],
        PARAMS["initial_prices"],
        sender=account,
    )
    pool = project.CurveTricryptoOptimizedWETH.at(
        tx.events.filter(factory.TricryptoPoolDeployed)[0].pool
    )
    logger.info(f"Success! Deployed pool at {pool}!")

    # ---------------------------- SWAP TESTS --------------------------------

    deploy_utils.test_deployment(pool, coins, fee_receiver, account)

    # -------------------------- GAUGE DEPLOYMENT ----------------------------

    logger.info("Deploying Gauge:")
    tx = factory.deploy_gauge(pool, sender=account)
    gauge = project.LiquidityGauge.at(
        tx.events.filter(factory.LiquidityGaugeDeployed)[0].gauge
    )

    # ------------------- CURVE DAO RELATED CODE -----------------------------

    logger.info("Adding gauge to the gauge controller:")
    vote_id = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP,
        [
            (deploy_utils.GAUGE_CONTROLLER, "add_gauge", gauge.address, 5, 0),
        ],
        "Add tricryptoUSDC [ethereum] gauge to the gauge controller",
        account,
    )

    logger.info("Tranfer factory ownership to the DAO")
    factory.commit_transfer_ownership(owner, sender=account)
    assert factory.future_admin() == owner

    logger.info("Create vote for the DAO to accept ownership of the factory")
    vote_id = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP,
        [
            (factory.address, "accept_transfer_ownership"),
        ],
        "Accept ownership of optimized tricrypto factory [Ethereum]",
        account,
    )

    if is_sim:
        logger.info("Simulate and check DAO Vote outcomes:")
        simulate(vote_id, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert (
            Contract(deploy_utils.GAUGE_CONTROLLER).gauge_types(gauge.address)
            == 5
        )

        simulate(vote_id, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert factory.admin() == owner

    # ------------- ADDRESSPROVIDER AND METAREGISTRY INTEGRATION -------------

    logger.info("Integrate into AddressProvider and Metaregistry ...")
    logger.info(
        "Deploying Factory handler to integrate it to the metaregistry:"
    )
    factory_handler = account.deploy(  # noqa: F841
        project.CurveTricryptoFactoryHandler, factory.address
    )

    if is_sim:
        breakpoint()
