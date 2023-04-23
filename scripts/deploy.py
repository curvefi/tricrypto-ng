import warnings

import click
from ape import Contract, accounts, project
from ape.cli import NetworkBoundCommand, account_option, network_option
from ape.logging import logger
from eth_utils import to_checksum_address

import scripts.deployment_utils as deploy_utils
from scripts.simulate import simulate
from scripts.vote_utils import make_vote

warnings.filterwarnings("ignore")


def _deploy_metaregistry_integration(network, account, factory, pool):

    assert "ethereum" in network
    is_sim = "mainnet-fork" in network

    logger.info("Integrate into AddressProvider and Metaregistry ...")
    logger.info(
        "Deploying Factory handler to integrate it to the metaregistry:"
    )
    factory_handler = account.deploy(
        project.CurveTricryptoFactoryHandler, factory.address
    )

    if is_sim:

        # Test metaregistry integration:
        metaregistry = Contract("0xF98B45FA17DE75FB1aD0e7aFD971b0ca00e379fC")
        metaregistry_admin = accounts[metaregistry.owner()]
        metaregistry.add_registry_handler(
            factory_handler, sender=metaregistry_admin
        )

        registry_handlers = metaregistry.get_registry_handlers_from_pool(pool)
        balances = [pool.balances(i) for i in range(3)] + [0] * 5

        assert metaregistry.is_registered(pool)
        assert factory_handler in registry_handlers
        assert metaregistry.get_balances(pool) == balances


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_ethereum(network, account):

    assert "ethereum" in network, "Only Ethereum supported."

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

    # --------------------- DEPLOY FACTORY AND POOL ---------------------------

    factory = deploy_utils.deploy_amm_factory(fee_receiver, account, weth)

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

    # ------------------- GAUGE IMPLEMENTATION DEPLOYMENT --------------------

    logger.info("Deploying gauge blueprint contract:")
    gauge_impl = deploy_utils.deploy_blueprint(project.LiquidityGauge, account)

    logger.info("Set Gauge Implementation:")
    factory.set_gauge_implementation(gauge_impl, sender=account)

    # ------------- ADDRESSPROVIDER AND METAREGISTRY INTEGRATION -------------

    _deploy_metaregistry_integration(network, account, factory, pool)

    print("Success!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def test_pool_deployment(network, account, pool):

    assert "ethereum" in network, "Only Ethereum supported."

    coins = [
        to_checksum_address(pool.coins(0)),
        to_checksum_address(pool.coins(1)),
        to_checksum_address(pool.coins(2)),
    ]
    fee_receiver = pool.fee_receiver()

    # Test liquidity actions in deployed pool:
    deploy_utils.test_deployment(pool, coins, fee_receiver, account)


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--factory", required=True, type=str)
def transfer_factory_to_dao(network, account, factory):

    assert "ethereum" in network
    is_sim = "mainnet-fork" in network

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract

    assert factory is not None

    logger.info("Tranfer factory ownership to the DAO")
    factory.commit_transfer_ownership(owner, sender=account)
    assert factory.future_admin() == owner

    logger.info("Create vote for the DAO to accept ownership of the factory")
    vote_id_dao_ownership = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP,
        [
            (factory.address, "accept_transfer_ownership"),
        ],
        "Accept ownership of optimized tricrypto factory [Ethereum]",
        account,
    )

    if is_sim:
        logger.info("Simulate and check DAO Vote outcomes:")
        simulate(
            vote_id_dao_ownership, deploy_utils.CURVE_DAO_OWNERSHIP["voting"]
        )
        assert factory.admin() == owner


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--pool", required=True, type=str)
@click.option("--factory", required=True, type=str)
def deploy_gauge_and_set_up_vote(network, account, pool, factory):

    assert "ethereum" in network
    is_sim = "mainnet-fork" in network

    logger.info("Deploying Gauge:")
    tx = factory.deploy_gauge(pool, sender=account)
    gauge = project.LiquidityGauge.at(  # noqa: F841
        tx.events.filter(factory.LiquidityGaugeDeployed)[0].gauge
    )

    logger.info("Adding gauge to the gauge controller:")
    vote_id_gauge = make_vote(
        deploy_utils.CURVE_DAO_OWNERSHIP,
        [
            (deploy_utils.GAUGE_CONTROLLER, "add_gauge", gauge.address, 5, 0),
        ],
        "Add tricryptoUSDC [ethereum] gauge to the gauge controller",
        account,
    )

    if is_sim:

        simulate(vote_id_gauge, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert (
            Contract(deploy_utils.GAUGE_CONTROLLER).gauge_types(gauge.address)
            == 5
        )
