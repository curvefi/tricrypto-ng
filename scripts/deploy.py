import warnings

import click
from ape import Contract, accounts, networks, project
from ape.cli import NetworkBoundCommand, account_option, network_option
from ape.logging import logger
from eth_abi import encode
from eth_utils import to_checksum_address
from hexbytes import HexBytes

import scripts.deployment_utils as deploy_utils
from scripts.simulate import simulate
from scripts.vote_utils import make_vote

warnings.filterwarnings("ignore")


def _test_metaregistry_integration(network, factory_handler, pool):

    assert "ethereum" in network
    is_sim = "mainnet-fork" in network

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
def deploy_factory(network, account):

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract
            fee_receiver = data.fee_receiver_address
            weth = to_checksum_address(data.weth_address)

    assert owner, f"Curve's DAO contracts may not be on {network}."
    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    deployed_contracts = {}
    if "ethereum:mainnet" in network:
        deployed_contracts = {
            "math": "0x53cc3e49418380E835fC8caCD5932482c586eFEa",
            "views": "0x3139Bf97B6376386b8cd1c5919554F055fa2A2AE",
            "amm_impl": "0x96EE7fD5023d1171a22fEDB178aeA82912a39Fbd",
            "factory": "0x01Bb983A4Ac1790DdA8514166ba46454139ccc39",
        }

    # --------------------- DEPLOY FACTORY AND POOL ---------------------------

    factory = deploy_utils.deploy_amm_factory(
        account, fee_receiver, weth, deployed_contracts
    )

    # ------------------- GAUGE IMPLEMENTATION DEPLOYMENT --------------------

    logger.info("Deploying gauge blueprint contract:")
    gauge_impl = deploy_utils.deploy_blueprint(project.LiquidityGauge, account)

    logger.info("Set Gauge Implementation:")
    factory.set_gauge_implementation(
        gauge_impl, sender=account, **deploy_utils._get_tx_params()
    )

    # ------------- ADDRESSPROVIDER AND METAREGISTRY INTEGRATION -------------

    if "ethereum:mainnet" in network:  # only supported in ethereum so far ...
        logger.info("Integrate into AddressProvider and Metaregistry ...")
        logger.info(
            "Deploying Factory handler to integrate it to the metaregistry:"
        )
        account.deploy(
            project.CurveTricryptoFactoryHandler,
            factory.address,
            **deploy_utils._get_tx_params(),
        )

    print("Success!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--factory", required=True, type=str)
def deploy_pool_via_factory(network, account, factory):

    PARAMS = deploy_utils.get_tricrypto_usdc_params()

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if f"{_network}:" in network:

            coins = [
                to_checksum_address(data.usdc_address),
                to_checksum_address(data.wbtc_address),
                to_checksum_address(data.weth_address),
            ]
            weth = to_checksum_address(data.weth_address)
            PARAMS["coins"] = coins

    logger.info("Deploying Pool:")
    factory = project.CurveTricryptoFactory.at(factory)
    tx = factory.deploy_pool(
        PARAMS["name"],
        PARAMS["symbol"],
        PARAMS["coins"],
        weth,
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
        **deploy_utils._get_tx_params(),
    )
    pool = project.CurveTricryptoOptimizedWETH.at(
        tx.events.filter(factory.TricryptoPoolDeployed)[0].pool
    )
    logger.info(f"Success! Deployed pool at {pool}!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_pool_directly(network, account):

    assert "ethereum:sepolia" in network

    PARAMS = [
        "TricryptoUSDC",
        "crvUSDCWBTCWETH",
        [
            "0x51fce89b9f6d4c530698f181167043e1bb4abf89",
            "0xff82bb6db46ad45f017e2dfb478102c7671b13b3",
            "0xf531b8f309be94191af87605cfbf600d71c2cfe0",
        ],
        "0x8764ADd5e7008ac9a1F44f2664930e8c8fdDc095",
        "0xf531B8F309Be94191af87605CfBf600D71C2cFe0",
        HexBytes(
            "0xa5c6fa39ec823ba77119dea718f2f5a448843c0d9e6e3882ab8ef075aeb9df96"  # noqa: E501
        ),
        340282366920938463463559074872505306972160000000001,
        581076037942835227425498917514114728328226821,
        1020847100762815390943526144507091182848000000,
        680564733841876935965653810981216714752000000000865,
        632244637739103665114950020608225336913174000000000000000000,
    ]

    logger.info("Deploying Pool replica:")
    project.CurveTricryptoOptimizedWETH.deploy(
        *PARAMS,
        sender=account,
        **deploy_utils._get_tx_params(),
    )

    logger.info("Success!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--pool", required=True, type=str)
def withdraw_all_from_pool(network, account, pool):

    pool = project.CurveTricryptoOptimizedWETH.at(pool)
    token_balance = pool.balanceOf(account)
    total_supply = pool.totalSupply()

    deposit_ratio = token_balance / total_supply

    min_amt_received = [
        int(0.99 * pool.balances(0) * deposit_ratio),
        int(0.99 * pool.balances(1) * deposit_ratio),
        int(0.99 * pool.balances(2) * deposit_ratio),
    ]

    logger.info(
        f"Removing {token_balance} liquidity to receive at least "
        f"{min_amt_received} underlying tokens."
    )
    tx = pool.remove_liquidity(
        token_balance, min_amt_received, True, sender=account
    )
    tokens_received = tx.events.filter(pool.RemoveLiquidity)[0].token_amounts
    logger.info(f"Removed! Received {tokens_received} amount of coins.")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--pool", required=True, type=str)
def test_deployed_pool(network, account, pool):

    pool = project.CurveTricryptoOptimizedWETH.at(pool)
    fee_receiver = pool.fee_receiver()
    coins = [
        to_checksum_address(pool.coins(0)),
        to_checksum_address(pool.coins(1)),
        to_checksum_address(pool.coins(2)),
    ]

    # Test liquidity actions in deployed pool:
    deploy_utils.test_deployment(pool, coins, fee_receiver, account)


@cli.command(cls=NetworkBoundCommand)
@network_option()
# @account_option()
@click.option("--tx", required=True, type=str)
def get_encoded_constructor_args(network, tx):

    tx_object = networks.active_provider.get_receipt(tx)
    logs = tx_object.decode_logs()
    for log in logs:
        if log.event_name == "TricryptoPoolDeployed":
            break

    packed = lambda x: (x[0] << 128) | (x[1] << 64) | x[2]  # noqa: E731
    unpacked = lambda x: [  # noqa: E731
        (x >> 128) & 18446744073709551615,
        (x >> 64) & 18446744073709551615,
        x & 18446744073709551615,
    ]

    precisions = []
    for i in range(3):
        d = project.ERC20Mock.at(log.coins[i]).decimals()
        assert d < 19, "Max 18 decimals for coins"
        precisions.append(10 ** (18 - d))

    # pack precisions
    packed_precisions = packed(precisions)
    assert unpacked(packed_precisions) == precisions

    # pack fees
    fee_params = [log.mid_fee, log.out_fee, log.fee_gamma]
    packed_fee_params = packed(fee_params)
    assert unpacked(packed_fee_params) == fee_params

    # pack liquidity rebalancing params
    rebalancing_params = [
        log.allowed_extra_profit,
        log.adjustment_step,
        log.ma_exp_time,
    ]
    packed_rebalancing_params = packed(rebalancing_params)
    assert unpacked(packed_rebalancing_params) == rebalancing_params

    # pack A_gamma
    packed_A_gamma = log.A << 128
    packed_A_gamma = packed_A_gamma | log.gamma

    # pack initial prices
    PRICE_SIZE = 256 // 2
    PRICE_MASK = 2**PRICE_SIZE - 1
    packed_prices = 0
    for k in range(2):
        packed_prices = packed_prices << PRICE_SIZE
        p = log.initial_prices[1 - k]
        assert p < PRICE_MASK
        packed_prices = p | packed_prices

    pool = project.CurveTricryptoOptimizedWETH.at(log.pool)
    weth = pool.coins(2)
    assert project.ERC20Mock.at(weth).symbol() == "WETH"

    args = [
        pool.name(),
        pool.symbol(),
        log.coins,
        pool.MATH(),
        weth,
        log.salt,
        packed_precisions,
        packed_A_gamma,
        packed_fee_params,
        packed_rebalancing_params,
        packed_prices,
    ]
    constructor_abi = [
        "string",
        "string",
        "address[3]",
        "address",
        "address",
        "bytes32",
        "uint256",
        "uint256",
        "uint256",
        "uint256",
        "uint256",
    ]

    constructor_args = encode(constructor_abi, args).hex()

    logger.info(f"Constructor args: \n\n{args}\n")
    logger.info(f"Constructor code: \n\n{constructor_args}\n")

    return args


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--factory", required=True, type=str)
def transfer_factory_to_dao(network, account, factory):

    assert "ethereum:mainnet" in network
    is_sim = "mainnet-fork" in network

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract

    assert factory is not None

    logger.info("Tranfer factory ownership to the DAO")
    factory.commit_transfer_ownership(
        owner, sender=account, **deploy_utils._get_tx_params()
    )
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

    assert "ethereum:mainnet" in network
    is_sim = "mainnet-fork" in network

    logger.info("Deploying Gauge:")
    tx = factory.deploy_gauge(
        pool, sender=account, **deploy_utils._get_tx_params()
    )
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
