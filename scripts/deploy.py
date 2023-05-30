import math
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

DEPLOYED_CONTRACTS = {
    "ethereum:mainnet": {
        "factory": "0x0c0e5f2fF0ff18a3be9b835635039256dC4B4963",
        "math": "0xcBFf3004a20dBfE2731543AA38599A526e0fD6eE",
        "views": "0x064253915b8449fdEFac2c4A74aA9fdF56691a31",
        "amm_impl": "0x66442B0C5260B92cAa9c234ECf2408CBf6b19a6f",
        "gauge_impl": "0x5fC124a161d888893529f67580ef94C2784e9233",
        "factory_handler": "0x5c57f810665E9aafb753bB9e38E6C467a6Bc4a25",
    }
}


def _deploy_pool_from_factory(
    network, account, factory, weth, PARAMS=None
):  # noqa: E501

    if PARAMS is None:
        PARAMS = deploy_utils.get_tricrypto_usdc_params()

    coins = []
    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if f"{_network}" in network:

            coins = [
                to_checksum_address(data.usdc_address),
                to_checksum_address(data.wbtc_address),
                to_checksum_address(data.weth_address),
            ]
            weth = to_checksum_address(data.weth_address)
            PARAMS["coins"] = coins
            break

    assert coins is not None

    logger.info("Deploying Pool:")
    factory = project.CurveTricryptoFactory.at(factory)
    tx = factory.deploy_pool(
        PARAMS["name"],
        PARAMS["symbol"],
        coins,
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
    _get_encoded_constructor_args(tx, PARAMS)

    return pool


def _get_encoded_constructor_args(tx, PARAMS):

    if type(tx) is str:
        tx_object = networks.active_provider.get_receipt(tx)
    else:
        tx_object = tx

    logs = tx_object.decode_logs()
    for log in logs:
        if log.event_name == "TricryptoPoolDeployed":
            break

    pool = project.CurveTricryptoOptimizedWETH.at(log.pool)

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
    fee_params = [pool.mid_fee(), pool.out_fee(), pool.fee_gamma()]
    assert log.packed_fee_params == packed(fee_params)

    # pack liquidity rebalancing params
    rebalancing_params = [
        pool.allowed_extra_profit(),
        pool.adjustment_step(),
        int(pool.ma_time() // math.log(2)),
    ]
    assert log.packed_rebalancing_params == packed(rebalancing_params)

    # pack A_gamma
    packed_A_gamma = pool.A() << 128
    packed_A_gamma = packed_A_gamma | pool.gamma()

    assert log.packed_A_gamma == packed_A_gamma

    # pack initial prices
    PRICE_SIZE = 256 // 2
    PRICE_MASK = 2**PRICE_SIZE - 1
    unpacked_prices = []
    packed_prices = log.packed_prices
    for k in range(2):
        unpacked_prices.append(packed_prices & PRICE_MASK)
        packed_prices = packed_prices >> PRICE_SIZE

    assert unpacked_prices == PARAMS["initial_prices"]

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
        packed(fee_params),
        packed(rebalancing_params),
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


@click.group(short_help="Deploy the project")
def cli():
    pass


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def deploy_and_test_infra(network, account):

    if "mainnet-fork" in network:
        account = accounts["0xbabe61887f1de2713c6f97e567623453d3c79f67"]

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract
            fee_receiver = data.fee_receiver_address
            weth = to_checksum_address(data.weth_address)

    assert owner, f"Curve's DAO contracts may not be on {network}."
    assert fee_receiver, f"Curve's DAO contracts may not be on {network}."

    # --------------------- DEPLOY FACTORY AND POOL ---------------------------

    factory = deploy_utils.deploy_amm_factory(
        account, fee_receiver, weth, network, DEPLOYED_CONTRACTS[network]
    )

    pool = _deploy_pool_from_factory(network, account, factory, weth)
    coins = [
        to_checksum_address(pool.coins(0)),
        to_checksum_address(pool.coins(1)),
        to_checksum_address(pool.coins(2)),
    ]

    _account = account
    if "mainnet-fork" in network:
        _account = accounts["0x8EB8a3b98659Cce290402893d0123abb75E3ab28"]

    deploy_utils.test_deployment(pool, coins, fee_receiver, _account)

    print("Success!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--factory", required=True, type=str)
def set_up_gauge(network, account, factory):

    factory = project.CurveTricryptoFactory.at(factory)

    if "ethereum:mainnet" not in network:
        return  # only applicable for ethereum mainnet

    # ------------------- GAUGE IMPLEMENTATION DEPLOYMENT --------------------
    logger.info("Deploying gauge blueprint contract:")
    gauge_impl = deploy_utils.deploy_blueprint(project.LiquidityGauge, account)

    logger.info("Set Gauge Implementation:")
    factory.set_gauge_implementation(
        gauge_impl, sender=account, **deploy_utils._get_tx_params()
    )


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def integrate_metaregistry(network, account):

    factory = project.CurveTricryptoFactory.at(
        DEPLOYED_CONTRACTS[network]["factory"]
    )  # noqa: E501

    if "ethereum:mainnet" not in network:
        return  # only applicable for ethereum mainnet

    pool = project.CurveTricryptoOptimizedWETH.at(factory.pool_list(0))
    metaregistry = Contract("0xF98B45FA17DE75FB1aD0e7aFD971b0ca00e379fC")
    boss = Contract(metaregistry.owner())

    # set up metaregistry integration:
    if not metaregistry.is_registered(pool):

        logger.info("Integrate into Metaregistry ...")
        logger.info(
            "Deploying Factory handler to integrate it to the metaregistry:"
        )
        factory_handler = account.deploy(
            project.CurveTricryptoFactoryHandler,
            factory.address,
            **deploy_utils._get_tx_params(),
        )

        boss.execute(
            metaregistry.address,
            metaregistry.add_registry_handler.encode_input(factory_handler),
            sender=account,
            **deploy_utils._get_tx_params(),
        )

        registry_handlers = metaregistry.get_registry_handlers_from_pool(pool)
        balances = [pool.balances(i) for i in range(3)] + [0] * 5

        # Test metaregistry integration:
        assert metaregistry.is_registered(pool)
        assert factory_handler in registry_handlers
        assert metaregistry.get_balances(pool) == balances

        logger.info("Metaregistry Integrated!")

    print("Done!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
def integrate_address_provider(network, account):

    assert "ethereum:mainnet" in network  # only for ethereum mainnet

    address_provider = Contract("0x0000000022d53366457f9d5e68ec105046fc4383")
    max_id = address_provider.max_id()
    description = "Curve Tricrypto Factory"
    boss = Contract(address_provider.admin())
    factory = DEPLOYED_CONTRACTS[network]["factory"]

    account_is_boss_handler = False
    for i in range(2):
        if account.address.lower() == boss.admins(i).lower():
            account_is_boss_handler = True
            break

    assert account_is_boss_handler  # only authorised accounts can write to address provider  # noqa: E501

    for index in range(max_id + 1):
        if address_provider.get_id_info(index).description is description:
            break

    if index == max_id:

        logger.info(f"Adding a new registry provider entry at id: {index + 1}")

        # we're adding a new id
        with accounts.use_sender(account) as account:
            boss.execute(
                address_provider.address,
                address_provider.add_new_id.encode_input(factory, description),
                gas_limit=400000,
                **deploy_utils._get_tx_params(),
            )

    else:

        assert address_provider.get_id_info(index).description == description

        logger.info(
            f"Updating existing registry provider entry at id: {index}"
        )

        # we're updating an existing id with the same description:
        with accounts.use_sender(account) as account:
            boss.execute(
                address_provider.address,
                address_provider.set_address.encode_input(index, factory),
                gas_limit=200000,
                **deploy_utils._get_tx_params(),
            )

    assert address_provider.get_id_info(index).addr.lower() == factory.lower()

    logger.info("AddressProvider integration complete!")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--id", required=True, type=int)
def clean_address_provider(network, account, id):

    address_provider = Contract("0x0000000022d53366457f9d5e68ec105046fc4383")
    boss = Contract(address_provider.admin())
    id_info = address_provider.get_id_info(id)
    assert id_info.addr != "0x0000000000000000000000000000000000000000"

    logger.info(
        f"Cleaning existing entry in registry provider entry at id: {id}"
    )  # noqa: E501
    logger.info(f"Description at id {id}: {id_info.description}")
    logger.info(
        f"Contract address being cleaned up: {Contract(id_info.addr)}"
    )  # noqa: E501

    # keep check of what was previously in the address provider:
    previous_entries = []
    for i in range(address_provider.max_id() + 1):
        id_info = address_provider.get_id_info(i)
        previous_entries.append((id_info.addr, id_info.description))

    with accounts.use_sender(account) as account:
        boss.execute(
            address_provider.address,
            address_provider.unset_address.encode_input(id),
            gas_limit=200000,
            **deploy_utils._get_tx_params(),
        )

    for i in range(address_provider.max_id() + 1):
        id_info = address_provider.get_id_info(i)
        assert previous_entries[i][1] == id_info.description
        if i != id:
            assert previous_entries[i][0] == id_info.addr
        else:
            assert id_info.addr == "0x0000000000000000000000000000000000000000"

    logger.info(
        f"Successfully and safuly unset id: {id} in AddressProvider on {network}!"  # noqa: E501
    )


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
def withdraw_liquidity(network, account, pool):

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
        token_balance,
        min_amt_received,
        False,
        sender=account,
        **deploy_utils._get_tx_params(),
    )
    tokens_received = tx.events.filter(pool.RemoveLiquidity)[0].token_amounts
    logger.info(f"Removed! Received {tokens_received} amount of coins.")


@cli.command(cls=NetworkBoundCommand)
@network_option()
@account_option()
@click.option("--pool", required=True, type=str)
def test_deployed_pool(network, account, pool):

    if "mainnet-fork" in network:
        account = accounts[
            "0x8EB8a3b98659Cce290402893d0123abb75E3ab28"
        ]  # AVAX bridge  # noqa: E501

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
@account_option()
@click.option("--factory", required=True, type=str)
def transfer_factory_to_dao(network, account, factory):

    assert "ethereum:mainnet" in network
    is_sim = "mainnet-fork" in network

    for _network, data in deploy_utils.curve_dao_network_settings.items():

        if _network in network:

            owner = data.dao_ownership_contract

    assert factory is not None

    factory = project.CurveTricryptoFactory.at(factory)
    assert factory.admin() == account

    logger.info("Tranfer factory ownership to the DAO")
    factory.commit_transfer_ownership(
        owner,
        sender=account,
        gas_limit=200000,
        **deploy_utils._get_tx_params(),
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
        "Add tricryptoUSDC Ethereum gauge to the gauge controller",
        account,
    )

    if is_sim:

        simulate(vote_id_gauge, deploy_utils.CURVE_DAO_OWNERSHIP["voting"])
        assert (
            Contract(deploy_utils.GAUGE_CONTROLLER).gauge_types(gauge.address)
            == 5
        )
